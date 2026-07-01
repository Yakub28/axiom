"""OpenAlex ingestion — the data-layer seam (decision: OpenAlex -> SQLite).

Builds the corpus by SNOWBALL / 2-hop expansion (decision OD7): seed on a topic,
then pull in the papers the seeds cite *and* the papers that cite the seeds, so
the citation graph is connected rather than a star of dangling external edges.

Writes through the frozen db.insert_* helpers, so the shared schema/contract is
untouched. Citation edges keep dangling externals (dst outside the corpus) by
design — the schema has no FK on citation_edges.dst_id for exactly this reason.

This module is PURE-PYTHON (httpx only): it does NOT import torch/transformers,
so the fetch path runs on any Python. Embedding/upsert lives in axiom.indexer.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Iterator

import httpx

from axiom import config, db


# ---------------------------------------------------------------------------
# Parsed shapes
# ---------------------------------------------------------------------------
@dataclass
class ParsedWork:
    """One OpenAlex work, normalized to our schema's columns."""
    openalex_id: str
    title: str | None
    abstract: str | None
    publication_year: int | None
    venue_id: str | None
    venue: str | None
    cited_by_count: int
    doi: str | None
    concepts: list[tuple[str, int]] = field(default_factory=list)   # (name, level)
    references: list[str] = field(default_factory=list)             # short dst ids


# ---------------------------------------------------------------------------
# Pure helpers (no network) — easy to unit-test
# ---------------------------------------------------------------------------
def short_id(openalex_id: str | None) -> str | None:
    """'https://openalex.org/W2741809807' -> 'W2741809807' (idempotent)."""
    if not openalex_id:
        return None
    return openalex_id.rsplit("/", 1)[-1]


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Rebuild plain text from OpenAlex's abstract_inverted_index.

    OpenAlex stores abstracts as {word: [positions]}. We invert it back to a
    position-ordered string (decision: abstracts reconstructed before insert).
    """
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort(key=lambda p: p[0])
    return " ".join(word for _, word in positions)


def parse_work(work: dict) -> ParsedWork:
    """Map a raw OpenAlex work JSON onto our schema columns."""
    venue_id = None
    venue = None
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    if source:
        venue_id = short_id(source.get("id"))
        venue = source.get("display_name")

    concepts = [
        (c["display_name"], c.get("level"))
        for c in (work.get("concepts") or [])
        if c.get("display_name")
    ]
    references = [short_id(r) for r in (work.get("referenced_works") or [])]
    references = [r for r in references if r]

    return ParsedWork(
        openalex_id=short_id(work.get("id")),
        title=work.get("title"),
        abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
        publication_year=work.get("publication_year"),
        venue_id=venue_id,
        venue=venue,
        cited_by_count=work.get("cited_by_count") or 0,
        doi=work.get("doi"),
        concepts=concepts,
        references=references,
    )


def _chunked(items: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


# ---------------------------------------------------------------------------
# OpenAlex HTTP client (polite pool, paging, retries)
# ---------------------------------------------------------------------------
# Only the fields we actually use, to keep responses small/fast.
_WORK_FIELDS = ",".join([
    "id", "title", "abstract_inverted_index", "publication_year",
    "primary_location", "cited_by_count", "doi", "concepts", "referenced_works",
])


class OpenAlexClient:
    def __init__(self, mailto: str | None = None, client: httpx.Client | None = None):
        self.base = config.OPENALEX_BASE
        self.mailto = mailto or config.OPENALEX_MAILTO
        self._client = client or httpx.Client(
            base_url=self.base, timeout=config.OPENALEX_TIMEOUT
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OpenAlexClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "mailto": self.mailto}
        last_exc: Exception | None = None
        for attempt in range(config.OPENALEX_MAX_RETRIES):
            try:
                resp = self._client.get(path, params=params)
                if resp.status_code == 429:               # rate limited — back off
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError,) as exc:
                last_exc = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"OpenAlex GET {path} failed after retries") from last_exc

    def search_seeds(self, query: str, count: int) -> list[dict]:
        """Most *relevant* works matching `query` — the snowball seed set.

        Uses the `title_and_abstract.search` filter with OpenAlex's default
        relevance ranking. A plain `cited_by_count:desc` sort is wrong here: it
        surfaces the most-cited papers in the whole index that merely contain
        the tokens (SciPy, QUANTUM ESPRESSO, ...), not on-topic work.
        """
        data = self._get("/works", {
            "filter": f"title_and_abstract.search:{query}",
            "per-page": min(count, 200),
            "select": _WORK_FIELDS,
        })
        return data.get("results", [])[:count]

    def works_by_ids(self, ids: list[str]) -> list[dict]:
        """Fetch metadata for specific works via an OR filter on openalex_id."""
        out: list[dict] = []
        for batch in _chunked(ids, config.OPENALEX_BATCH_SIZE):
            data = self._get("/works", {
                "filter": "openalex_id:" + "|".join(batch),
                "per-page": len(batch),
                "select": _WORK_FIELDS,
            })
            out.extend(data.get("results", []))
        return out

    def citers(self, paper_id: str, limit: int) -> list[dict]:
        """Works that cite `paper_id`, most-cited first (capped at `limit`)."""
        data = self._get("/works", {
            "filter": f"cites:{paper_id}",
            "sort": "cited_by_count:desc",
            "per-page": min(limit, 200),
            "select": _WORK_FIELDS,
        })
        return data.get("results", [])[:limit]


# ---------------------------------------------------------------------------
# Snowball: seed -> expand cited + citers -> ~target papers
# ---------------------------------------------------------------------------
def snowball(
    client: OpenAlexClient,
    *,
    seed_query: str | None = None,
    target: int | None = None,
    seed_count: int | None = None,
    citers_per_seed: int | None = None,
    log=print,
) -> dict[str, dict]:
    """Return {short_id: raw_work} for a connected ~`target`-paper neighborhood.

    Strategy per hop:
      1. From the current frontier, count how often each *cited* work is
         referenced (co-citation frequency) — central papers rank highest.
      2. Pull citers of frontier papers (already-fetched metadata, free edges).
      3. Fetch metadata for the top cited candidates until we reach `target`.
    """
    seed_query = seed_query or config.SEED_QUERY
    target = target or config.CORPUS_TARGET
    seed_count = seed_count or config.SEED_COUNT
    citers_per_seed = citers_per_seed if citers_per_seed is not None else config.CITERS_PER_SEED

    works: dict[str, dict] = {}
    seeds = client.search_seeds(seed_query, seed_count)
    for w in seeds:
        sid = short_id(w.get("id"))
        if sid:
            works[sid] = w
    log(f"[ingest] {len(works)} seeds for query={seed_query!r}")

    frontier = list(works.keys())
    hop = 0
    while frontier and len(works) < target:
        hop += 1
        next_frontier: list[str] = []

        # 1. citers of frontier papers (capped) — adds citer->frontier edges.
        for sid in frontier:
            if len(works) >= target:
                break
            for w in client.citers(sid, citers_per_seed):
                cid = short_id(w.get("id"))
                if cid and cid not in works:
                    works[cid] = w
                    next_frontier.append(cid)
                    if len(works) >= target:
                        break

        # 2. cited works ranked by co-citation frequency across the frontier.
        cited_freq: Counter[str] = Counter()
        for sid in frontier:
            for ref in (works[sid].get("referenced_works") or []):
                rid = short_id(ref)
                if rid and rid not in works:
                    cited_freq[rid] += 1

        need = target - len(works)
        if need > 0 and cited_freq:
            to_fetch = [rid for rid, _ in cited_freq.most_common(need)]
            for w in client.works_by_ids(to_fetch):
                wid = short_id(w.get("id"))
                if wid and wid not in works:
                    works[wid] = w
                    next_frontier.append(wid)

        log(f"[ingest] hop {hop}: corpus={len(works)} (+{len(next_frontier)})")
        frontier = next_frontier

    return works


# ---------------------------------------------------------------------------
# Write parsed works into SQLite (idempotent: wipes prior rows first)
# ---------------------------------------------------------------------------
def ingest_to_sqlite(
    conn,
    works: Iterable[dict],
    *,
    source: str = "openalex",
    log=print,
) -> int:
    """Parse + write works to SQLite. Returns the paper count written.

    Citation edges are written for EVERY referenced_work, including dangling
    ones whose dst is outside the corpus (kept by design — flagged downstream
    in the graph layer as in_corpus=False).
    """
    db.init_db(conn)
    # Idempotent clean slate (mirrors the synthetic bootstrap).
    for table in ("concepts", "citation_edges", "paper_provenance", "papers"):
        conn.execute(f"DELETE FROM {table}")

    parsed = [parse_work(w) for w in works]
    parsed = [p for p in parsed if p.openalex_id]

    for p in parsed:
        db.insert_paper(
            conn,
            openalex_id=p.openalex_id,
            title=p.title,
            abstract=p.abstract,
            publication_year=p.publication_year,
            venue_id=p.venue_id,
            venue=p.venue,
            cited_by_count=p.cited_by_count,
            doi=p.doi,
        )
        if p.concepts:
            db.insert_concepts(conn, p.openalex_id, p.concepts)
        db.insert_provenance(
            conn, paper_id=p.openalex_id, source=source,
            abstract=p.abstract, has_fulltext=False,
        )
        if p.references:
            db.insert_citation_edges(
                conn,
                [(p.openalex_id, dst, p.publication_year) for dst in p.references],
            )
    conn.commit()

    edge_count = conn.execute("SELECT COUNT(*) AS n FROM citation_edges").fetchone()["n"]
    log(f"[ingest] wrote {len(parsed)} papers, {edge_count} citation edges to {config.DB_PATH}")
    return len(parsed)

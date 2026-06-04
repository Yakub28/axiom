"""SQLite access layer for Axiom.

Thin helpers around the shared schema (db/schema.sql). Keeps all SQL in one
place so the data contract is enforced from a single module.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Sequence

from axiom import config


def connect(db_path=None) -> sqlite3.Connection:
    """Open a connection with foreign keys on and row access by column name."""
    path = str(db_path or config.DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables/indexes from the shared schema (idempotent)."""
    sql = config.SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def text_hash(text: str | None) -> str:
    """Stable hash of abstract text for dedup / change detection."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def insert_paper(
    conn: sqlite3.Connection,
    *,
    openalex_id: str,
    title: str | None,
    abstract: str | None,
    publication_year: int | None,
    venue_id: str | None,
    venue: str | None,
    cited_by_count: int = 0,
    doi: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO papers
            (openalex_id, title, abstract, publication_year,
             venue_id, venue, cited_by_count, doi)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (openalex_id, title, abstract, publication_year,
         venue_id, venue, cited_by_count, doi),
    )


def insert_concepts(
    conn: sqlite3.Connection,
    paper_id: str,
    concepts: Iterable[tuple[str, int]],
) -> None:
    """concepts: iterable of (concept_name, level)."""
    conn.executemany(
        "INSERT INTO concepts (paper_id, concept, level) VALUES (?, ?, ?)",
        [(paper_id, c, lvl) for c, lvl in concepts],
    )


def insert_citation_edges(
    conn: sqlite3.Connection,
    edges: Iterable[tuple[str, str, int | None]],
) -> None:
    """edges: iterable of (src_id, dst_id, year)."""
    conn.executemany(
        "INSERT INTO citation_edges (src_id, dst_id, year) VALUES (?, ?, ?)",
        list(edges),
    )


def insert_provenance(
    conn: sqlite3.Connection,
    *,
    paper_id: str,
    source: str,
    abstract: str | None,
    has_fulltext: bool = False,
    fetched_at: datetime | None = None,
) -> None:
    ts = (fetched_at or datetime.now(timezone.utc)).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO paper_provenance
            (paper_id, source, fetched_at, text_hash, has_fulltext)
        VALUES (?, ?, ?, ?, ?)
        """,
        (paper_id, source, ts, text_hash(abstract), has_fulltext),
    )


def distinct_venues(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT venue FROM papers WHERE venue IS NOT NULL ORDER BY venue"
    ).fetchall()
    return [r["venue"] for r in rows]


def year_bounds(conn: sqlite3.Connection) -> tuple[int, int] | None:
    row = conn.execute(
        "SELECT MIN(publication_year) AS lo, MAX(publication_year) AS hi FROM papers"
    ).fetchone()
    if row is None or row["lo"] is None:
        return None
    return int(row["lo"]), int(row["hi"])


def iter_papers(conn: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    """All papers, for embedding/upsert during bootstrap."""
    return conn.execute(
        "SELECT openalex_id, title, abstract, publication_year, "
        "venue, cited_by_count FROM papers"
    ).fetchall()


# TODO(P2): the ingestion track plugs in here — replace synthetic loading with
# OpenAlex fetch + inverted-index abstract reconstruction, writing into the same
# tables via these helpers so the contract stays stable.

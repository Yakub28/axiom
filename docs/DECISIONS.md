# Architecture Decisions

A running log of committed team decisions. **Any change to `db/schema.sql`
(the shared data contract) MUST be recorded here before merge.**

---

## OD6 — Graph store is NetworkX-first

NetworkX is the graph backend for P1/P2. **Do not introduce Neo4j now.** The
SQLite `citation_edges` table is the durable source of truth for edges (built
from OpenAlex `referenced_works[]`); the graph track loads it into NetworkX in
memory. Revisit a dedicated graph DB only if NetworkX becomes a bottleneck.

## Vector collection name = `axiom_v1`

The Qdrant collection is **versioned**: `axiom_v1`. Bump the suffix whenever the
embedding model or vector dimensionality changes so old and new points never mix.
One point per paper (abstract-level). Payload: `paper_id, title, year, venue,
cited_by_count, concepts[]`.

## Embedding model = `allenai/specter2_base` (768-dim)

SPECTER2 base, 768 dimensions. CPU fallback is allowed with a warning; we never
silently switch to a different model. P1 uses the base encoder with CLS pooling
over `title [SEP] abstract`. (P2 may add the SPECTER2 proximity adapter.)

## Data layer = OpenAlex → SQLite

OpenAlex is the source of truth. Abstracts arrive as an inverted index and must
be reconstructed to plain text before insertion into `papers.abstract`.

## `search()` signature (vector-store contract)

`AxiomQdrant.search(query_vector, top_k, venues=None, year_range=None)` returns
`list[SearchHit]`. Takes a **raw 768-dim vector** (the caller encodes), keeping
the vector store decoupled from the encoder. Facets AND together; `venues`
matches OR within the facet. Filters are applied natively by Qdrant. This
signature is frozen; new capability is added as new methods (e.g.
`search_hybrid`), never by changing it.

## Query-side embedding path = expansion (adapter blocked by pins)

Terse queries embed poorly when treated as documents. The preferred fix is the
SPECTER2 **ad-hoc query adapter**, but the `adapters` library pins
`transformers~=4.57`, conflicting with our committed `transformers==4.40.2`. We
do **not** bump pins, so the active path is **query expansion**: `encode_query`
wraps the query in `config.QUERY_EXPANSION_TEMPLATE` so it lands nearer the
document region. `Specter2Encoder` attempts the adapter import and logs the
active path (`[embed] query path: expansion`). Document-side encoding is
unchanged, so existing corpus points stay valid. Revisit the adapter if/when a
transformers pin bump is approved.

## Hybrid retrieval = dense + sparse, RRF-fused in Python (anticipated by D4/OD4)

Each point now stores **named vectors**: a dense SPECTER2 vector (`dense`) plus a
sparse BM25-style vector (`sparse`, pure-Python hashing-trick encoder in
`axiom/sparse.py`). `search_hybrid` runs both arms and fuses with Reciprocal
Rank Fusion. The pinned `qdrant-client==1.9.0` supports sparse vectors but **not**
the Query-API fusion primitives (`Prefetch`/`FusionQuery`, client ≥1.10), so
fusion is done in Python — no pin bump. The frozen `search` (pure dense) is
retained; the Streamlit page prefers `search_hybrid` when the collection has a
sparse vector. This is the documented win for exact terms/acronyms: query
`LoRA` now returns the *LoRA* paper at rank 1 (absent from dense top-5);
`RAG` returns the RAG paper at rank 1.

## OD7 — OpenAlex corpus is built by snowball / 2-hop expansion

Naively fetching N papers on a topic yields a graph that is almost all dangling
external edges (each paper's `referenced_works[]` mostly points outside the
fetched set), so the in-corpus citation graph is empty and every graph metric is
meaningless. Ingestion (`axiom/ingest.py`) therefore **snowballs**: seed on a
topic via the `title_and_abstract.search` filter (NOT `cited_by_count:desc`,
which returns globally-famous off-topic papers like SciPy), then expand by
pulling the papers the seeds cite *and* the papers that cite the seeds, ranking
cited candidates by co-citation frequency, until ~`CORPUS_TARGET` papers. This
densifies internal edges. OpenAlex needs no API key — only a `mailto` for the
polite pool. Abstracts are reconstructed from the inverted index before insert.
A first real run (`retrieval-augmented generation`, target 500) produced 500
papers / 1240 in-corpus edges (avg 2.5/paper), connected enough for PageRank.

## OD8 — Citation-graph influence = PageRank on the corpus-only subgraph

The graph (`axiom/graph.py`) loads `citation_edges` into a `networkx.DiGraph`
(edge `src->dst` = "src cites dst"), keeping dangling externals as nodes flagged
`in_corpus=False`. **Influence ranking runs PageRank on the corpus-only
subgraph** so metadata-less external sinks can't absorb rank; `local_in_degree`
(citations from within the corpus) is shown alongside as a transparent companion.
PageRank is a small **pure-Python power iteration** — we do NOT add `scipy` just
for `nx.pagerank` (keeps deps pinned/minimal; numpy/networkx only). This is the
NetworkX-first realisation of OD6; no Neo4j.

## OD9 — Research gaps = semantically-close, weakly-citing community pairs

The product's key value is surfacing **research gaps**, not just influence.
`axiom/gaps.py` detects them by combining the two signals we already have:
**structure** (citation graph) and **meaning** (SPECTER2 embeddings). Pipeline:
(1) Louvain community detection on the undirected corpus citation graph →
sub-topics; (2) label each community by its most *distinctive* OpenAlex concepts
(TF-IDF across communities, dropping near-universal terms like "Computer
science"); (3) an embedding centroid per community; (4) score community **pairs**
— `gap_score = centroid_cosine / (1 + inter_community_citations)`. High score =
related in meaning yet disconnected by citation = a bridge nobody has built.
NetworkX + numpy only (no scipy/torch). PageRank/influence is retained as a
companion view. Known limitation: on a sparse single-topic corpus, centroid
cosines cluster tightly (~0.95) and most cluster pairs have 0 inter-citations, so
discrimination is limited — denser/multi-topic corpora sharpen the signal.

---

## Schema change log

| Date       | Change                                              | By |
|------------|-----------------------------------------------------|----|
| 2026-06-04 | Initial P1 schema: papers, concepts, citation_edges, paper_provenance + read-path indexes | UI track |

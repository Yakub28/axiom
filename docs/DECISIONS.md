# Axiom — Architecture Decisions

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
matches OR within the facet. Filters are applied natively by Qdrant.

---

## Schema change log

| Date       | Change                                              | By |
|------------|-----------------------------------------------------|----|
| 2026-06-04 | Initial P1 schema: papers, concepts, citation_edges, paper_provenance + read-path indexes | UI track |

# LLMs for Sciences: Research Trends & Gaps Extraction Tool - Product Backlog

Axiom · full product backlog (P1-P4)

## Project Goal

**LLMs for Sciences: Research Trends & Gaps Extraction Tool** (Axiom) is a discovery platform for researchers and thesis seekers - not a paper search engine. It extracts two complementary signals from scholarly metadata: **research trends** (which concepts are accelerating via keyword velocity) and **research gaps** (under-explored conceptual regions validated by citation evidence and, for frontiers, an LLM hypothesis pitch grounded in real abstracts). Semantic search supports gap Step 1 geometry; the product centerpiece is trends + gaps extraction with mandatory HITL caveats.

---

## Implementation Status (as of 2026-07-01)

> **This backlog is the plan of record and now reflects what is actually built on
> branch `feat/hybrid-retrieval`.** Where the implementation diverged from the
> original plan, the task text has been rewritten to the as-built design and the
> superseded plan is kept inline as a note. Status markers throughout:
> ✅ Done · ⚠️ Partial / diverged · ❌ Not built. See `docs/DECISIONS.md`
> (OD6–OD9) and the `docs/21-06.md` work log for rationale.

**Built:** OpenAlex snowball ingest → SQLite → SPECTER2 → Qdrant with **hybrid
dense+sparse (RRF) retrieval** → **NetworkX** citation graph + PageRank influence
→ **OD9 research-gap detector** (community-pair, semantic-close / weakly-citing) →
Streamlit UI (Search tab + Citation-graph tab with a 3D force-directed viz and a
Research-gaps view).

**Diverged from plan:** corpus is **topic-snowball** (500 RAG papers, OD7), not
ACL-by-venue ≥1k · gap model is **OD9 community-pairs**, replacing the original
`s_max` + Scenario A/B + LangGraph-hypothesis pipeline · **NetworkX-only, no
Neo4j** (OD6) · the graph UX is a **3D WebGL** viz (the original "no 3D" scope
line is reversed — see Out of Scope).

**Still open:** velocity/trends engine (PBI 3), keyword/dataset extraction, the
LLM hypothesis + HITL pipeline (PBI 5), FastAPI (PBI 6), React + Trending/Reading-
List pages (PBI 7), 5k scale-up (T2.3), and calibration/eval (PBI 8).

---

## Critical Path Summary

**As-built spine (2026-07-01):** `OpenAlex (snowball) → SQLite → SPECTER2 →
Qdrant (hybrid dense+sparse / RRF) → NetworkX (PageRank) → OD9 gap detector →
Streamlit`. Neo4j is **dropped** (NetworkX-first, OD6); LangGraph, FastAPI, and
React remain **future** phases. The original full-stack target is retained below
for reference.

Build greenfield from empty repo to full stack: **OpenAlex → SQLite → SPECTER2 → Qdrant → Neo4j → LangGraph → FastAPI → React**. Saleh owns the data spine and index scale-up to 5k papers. Yahor owns velocity, the 3-step gap pipeline (WHERE → WHY → WHAT), agent graph, API contracts, and calibration. Yakub owns the four-page discovery dashboard (Trending, Keyword Graph, Gap Evaluator, Reading List) via Streamlit early integration then React from Stitch. NetworkX bootstraps citation logic before Neo4j Docker migration. Gap Step 3 (LangGraph 5-node graph with Verifier) runs only for Fertile Frontier verdicts. End-state demo: mentor filters ACL 2024-2025, spots rising RAG velocity, explores a ≤50-node keyword graph, evaluates a synthetic hypothesis through all 3 gap steps with badges and `supporting_paper_ids`, bookmarks a frontier candidate to Reading List with cited summaries. PBI 8 closes with τ calibration, nDCG@10 eval, and a reproducible README runbook.

## Phase Overview

| Phase | Goal | Key deliverables | Lead | Status |
|-------|------|------------------|------|--------|
| P1 | Data foundation | OpenAlex corpus, SQLite, SPECTER2, Qdrant (+hybrid), Streamlit search | Saleh | ✅ mostly (corpus is topic-snowball, not ACL-venue ≥1k) |
| P2 | Analytics core | NetworkX graph + PageRank, OD9 gap detector, Streamlit graph/gaps views | Yahor + Saleh | ⚠️ graph + gaps built; velocity engine & LangGraph not built |
| P3 | UI + agents integration | FastAPI, React 4 pages, LangGraph Step 3 full | Yakub + Yahor | ❌ not started (Streamlit only; Neo4j dropped, OD6) |
| P4 | Eval & scale | 5k corpus, calibration notebook, nDCG + gap quality study, runbook | All | ❌ not started (search-mode eval only) |

## Execution Order Table

| Seq | ID | Task / milestone | Depends on | Owner | Priority | Status |
|-----|-----|------------------|------------|-------|----------|--------|
| 1 | T1.1 | Repo scaffold, docker-compose skeleton, contracts + mocks | - | Yahor | High | ⚠️ scaffold ✅; `contracts/` mock layer not built; compose = Qdrant only, Neo4j dropped (OD6) |
| 2 | T1.2 | OpenAlex ingest + SQLite schema (topic snowball) | T1.1 | Saleh | High | ⚠️ ✅ but topic-snowball 500 papers (OD7), not ACL-venue ≥1k |
| 3 | T2.1 | SPECTER2 embedding pipeline | T1.2 | Saleh | High | ✅ |
| 4 | T2.2 | Qdrant collection + `search()` API | T2.1 | Saleh | High | ✅ |
| 4b | T2.5 | **Hybrid retrieval (dense+sparse BM25, RRF)** | T2.2 | Saleh | High | ✅ delivered extra (not in original plan) |
| 5 | T1.3 | Streamlit dev shell + page routing | T1.1 | Yakub | High | ✅ (Search + Citation-graph tabs) |
| 6 | T3.1 | Velocity engine + keyword storage | T1.2 | Yahor | High | ❌ not built |
| 7 | T3.2 | LLM keyword canonicalization | T3.1 | Yahor | Medium | ❌ not built |
| 8 | T4.1 | NetworkX citation graph builder | T1.2 | Yahor | High | ✅ + PageRank influence (OD8) |
| 9 | T4.2 | Gap detection | T2.2, T4.1 | Yahor | High | ⚠️→ superseded by **OD9** community-pair detector (not s_max + Scenario A/B) |
| 10 | T4.3 | ~~Neo4j Docker + migration~~ | T4.1 | Saleh | High | ❌→ dropped (OD6, NetworkX-first) |
| 11 | T4.4 | ~~Gap Step 2 on Neo4j Cypher~~ | T4.3, T4.2 | Saleh | High | ❌→ dropped (OD6) |
| 12 | T5.1 | LangGraph 5-node agent graph | T4.4, T3.1 | Yahor | High | ❌ not built |
| 13 | T5.2 | Gap Step 3 + composite G scoring + HITL queue backend | T5.1 | Yahor | High | ❌ not built |
| 14 | T6.1 | FastAPI service (search, trends, gap, reading list) | T2.2, T3.1, T5.2 | Yahor | High | ❌ not built |
| 15 | T7.1 | Trending Topics page (Streamlit then React) | T3.1, T6.1 | Yakub | High | ❌ not built (blocked on velocity) |
| 16 | T7.2 | Citation/keyword graph page | T3.1, T6.1 | Yakub | High | ⚠️→ delivered as **3D citation graph + Research-gaps view** (supersedes 2D ≤50-node) |
| 17 | T7.3 | Gap Evaluator page | T5.2, T6.1 | Yakub | High | ⚠️ OD9 Research-gaps view only; no 3-step badges / HITL / hypothesis UI |
| 18 | T7.4 | Reading List page (bookmarks + cited summaries) | T5.1, T6.1 | Yakub | High | ❌ not built |
| 19 | T2.3 | Corpus expansion to ≥5k (add NeurIPS 2024) | T2.2 | Saleh | High | ❌ at 500 |
| 20 | T2.4 | PDF extract pipeline (Marker/PyMuPDF) for intro chunks | T2.3 | Saleh | Medium | ❌ not built |
| 21 | T8.1 | Calibration notebook (τ, δ_D, δ_F) | T4.4, T5.2 | Yahor | High | ❌ not built |
| 22 | T8.2 | nDCG@10 + gap quality evaluation | T2.3, T5.2 | All | High | ⚠️ `scripts/eval_search.py` = retrieval-mode eval only; no nDCG@10 / gap-quality |
| 23 | T8.3 | README runbook + mentor demo package | T7.3, T8.1 | All | High | ⚠️ README + `docs/WALKTHROUGH.md` exist; no `demo_examples.md` / slides |
| 24 | T1.4 | `docs/DECISIONS.md` | - | Yahor | Medium | ✅ (logs OD6–OD9) |

---

## PBI 1 - Corpus & Data Foundation

**Status: ⚠️ mostly built.** Schema, ingest, and DECISIONS log are done; corpus is
topic-snowball (OD7) rather than ACL-by-venue ≥1k, and the `contracts/` mock layer
was never built (search exists as concrete methods).

### User Story:
As a researcher, I want a reliable scholarly corpus with citation metadata and provenance, so that all trend and gap extraction runs on trustworthy OpenAlex data.

### PBI Acceptance Criteria:
- SQLite schema stores papers, citation edges, keywords/concepts, and provenance per PROJECT_PLAN §6.1.
- Ingest reaches ≥1,000 ACL 2024-2025 papers with idempotent re-runs and exponential backoff on API errors.
- Citation edges from `referenced_works` are complete enough for graph construction (≥5k edges on 1k corpus).
- Ingest command and env vars documented in README.

### Task 1.1 - Repo Scaffold, Contracts & Dev Environment

- **Assignee:** Yahor
- **Sequence:** Y1
- **Priority:** High
- **Status:** ⚠️ Scaffold + `requirements.txt` + `docker-compose.yml` (Qdrant only) ✅. The typed `contracts/` package with mock stubs was **not** built — `search()`/`search_hybrid()` ship as concrete methods on `AxiomQdrant`. Neo4j is not in compose (dropped, OD6).

### Description:
- Create project layout per backlog §3.3: `ingest/`, `db/`, `embeddings/`, `index/`, `graph/`, `trends/`, `gap/`, `agents/`, `api/`, `app/`, `contracts/`, `eval/`, `docs/`.
- Add `requirements.txt`, `.env.example`, `docker-compose.yml` skeleton (Qdrant + Neo4j placeholders), README with course project goal.
- Define typed contracts with mock stubs: `search()`, `get_top_velocity_keywords()`, `evaluate_gap()`, `generate_hypothesis()`, `summarize_paper()`.

### Acceptance Criteria:
- Clean clone: `pip install -r requirements.txt` succeeds.
- `contracts/` modules export documented signatures; mocks return deterministic JSON matching Pydantic models.
- `docker compose up` starts Qdrant and Neo4j containers (Neo4j may be empty until T4.3).
- README states: **LLMs for Sciences: Research Trends & Gaps Extraction Tool**.

### Task 1.2 - OpenAlex Ingest + SQLite Schema

- **Assignee:** Saleh
- **Sequence:** S1
- **Priority:** High
- **Status:** ✅ Built as **topic snowball** (OD7), not ACL-by-venue.

### Description (as-built, OD7):
- Implemented `axiom/ingest.py` (pure-Python, no torch) + `db/schema.sql`: seed a
  topic via OpenAlex `title_and_abstract.search` (relevance), then **snowball /
  2-hop** — pull papers the seeds cite *and* papers that cite the seeds (cited
  candidates ranked by co-citation frequency) — until ~`CORPUS_TARGET`. This
  densifies in-corpus citation edges (a naive topic fetch yields an all-dangling
  graph). Cursor paging, retry/back-off, abstract reconstruction from the inverted
  index, persistence to `papers`, `citation_edges` (all `referenced_works`,
  including dangling externals), `paper_provenance`, concept fields.
- CLI: `scripts/ingest_openalex.py --topic <t> --target <n> [--seeds] [--no-index]`.

> **Original plan (superseded):** venue-based ingest targeting ≥1,000 ACL 2024–2025
> papers (`--venue ACL --years 2024,2025 --limit 1000`). Replaced by topic-snowball
> because citation analysis needs a *connected* corpus, not a venue slice.

### Acceptance Criteria:
- `python scripts/ingest_openalex.py --topic "retrieval-augmented generation" --target 500` completes without error.
- SQLite: ~500 papers, in-corpus citation edges sufficient for PageRank (first run: 500 papers / 1240 in-corpus edges), provenance with `fetched_at` and `text_hash`.
- Missing abstracts flagged; re-run is idempotent (wipe + reload).
- Ingest documented in README / `docs/21-06.md`.
- ❌ *Deferred:* reaching ≥1k and multi-venue breadth (see T2.3).

### Task 1.3 - Streamlit Dev Shell

- **Assignee:** Yakub
- **Sequence:** K1
- **Priority:** High
- **Status:** ✅ Built (structure differs from the 4-page plan).

### Description (as-built):
- `app/streamlit_app.py` with two tabs: **🔍 Search** (hybrid retrieval + venue/year
  filters) and **🕸️ Citation graph** (PageRank influence, 3D force-directed viz, and
  a Research-gaps view). Wires directly to the `axiom/*` modules (no contract mocks;
  no FastAPI yet). The Trending / Reading-List pages from the original 4-page plan
  are not built — see PBI 7.

> **Original plan (superseded):** sidebar routing across four pages (Trending →
> Keyword Graph → Gap Evaluator → Reading List) against T1.1 contract mocks.

### Acceptance Criteria:
- `streamlit run app/streamlit_app.py` starts; four pages render mock data matching contract shapes.
- Sidebar order: Trending → Keyword Graph → Gap Evaluator → Reading List.
- App title references course project name.

### Task 1.4 - Architecture Decisions Log

- **Assignee:** Yahor
- **Sequence:** Y2
- **Priority:** Medium
- **Status:** ✅ Built.

### Description (as-built):
- `docs/DECISIONS.md` records the live decisions: collection/embedding contracts,
  the `search()` signature, query-expansion path, **hybrid retrieval**, **OD6**
  (NetworkX-first, no Neo4j), **OD7** (snowball ingest), **OD8** (PageRank
  influence), **OD9** (community-pair gap detection), plus a schema change-log.

> **Original plan (superseded):** entries OD1–OD6 including an OD5 gap-badge
> sequence (Geometric Void → Citation Verified → Frontier Candidate). That badge
> model belonged to the superseded s_max/Scenario-A-B gap pipeline (see PBI 4/5).

---

## PBI 2 - Semantic Index & Search API

**Status: ✅ built + exceeded.** SPECTER2 + Qdrant `search()` done, plus a
delivered **hybrid dense+sparse (RRF)** arm not in the original plan (T2.5).
Corpus is at 500 (not 5k); PDF extraction not started.

### User Story:
As a gap detection pipeline, I need a semantic index over paper abstracts, so that Step 1 can measure geometric novelty (`s_max`) and search supports optional drill-down.

### PBI Acceptance Criteria:
- SPECTER2 embeddings for all papers with abstracts; title-only fallback flagged.
- Qdrant `axiom_v1` populated with hybrid payload filters (venue, year).
- `search(query, top_k, filters)` returns ranked results in <2s p95 on 1k corpus, <2s p95 on 5k after scale-up.
- Corpus expandable to ≥5k without schema redesign.

### Task 2.1 - SPECTER2 Batch Embedding Pipeline

- **Assignee:** Saleh
- **Sequence:** S2
- **Priority:** High
- **Status:** ✅ Built (`axiom/embed.py`, `axiom/indexer.py`; GPU/MPS→CPU fallback).

### Description:
- Implement `embeddings/specter2.py`: batch-encode abstracts from SQLite using `allenai/specter2_base`, 768-dim output keyed by `openalex_id`.

### Acceptance Criteria:
- `python -m embeddings.specter2 --db data/axiom.db` embeds ≥95% of papers (remainder title-only, flagged).
- Spot-check: related RAG pair cosine >0.7; unrelated pair <0.5.
- Embeddings persist and reload without re-encoding unchanged papers (hash check).

### Task 2.2 - Qdrant Collection + `search()` API

- **Assignee:** Saleh
- **Sequence:** S3
- **Priority:** High
- **Status:** ✅ Built (`axiom/qdrant_client.py`).

### Description:
- Implement `axiom/qdrant_client.py`: collection `axiom_v1`, cosine 768-dim, payload (`paper_id`, `year`, `venue`, `title`, `cited_by_count`, `concepts`), expose `search()`.

### Acceptance Criteria:
- One point per embedded paper; year/venue filters work.
- `search("RAG for low-resource NLP", top_k=10)` returns on-topic top results with scores.
- `AxiomQdrant.search(query_vector, top_k, venues, year_range)` signature frozen (DECISIONS); importable without UI.

---

### Task 2.5 - Hybrid Retrieval (dense + sparse, RRF) — *delivered, not in original plan*

- **Assignee:** Saleh
- **Priority:** High
- **Status:** ✅ Built.

### Description (as-built):
- Each point stores **named vectors**: dense SPECTER2 (`dense`) + a sparse
  BM25-style vector (`sparse`, pure-Python hashing-trick encoder in
  `axiom/sparse.py`). `search_hybrid()` runs both arms and fuses with **Reciprocal
  Rank Fusion** in Python (pinned `qdrant-client==1.9.0` lacks server-side fusion;
  no pin bump). The frozen dense `search()` is retained; Streamlit prefers
  `search_hybrid` when the collection has sparse vectors. Query-side embedding uses
  the expansion template (SPECTER2 adapter blocked by transformers pin).

### Acceptance Criteria:
- Exact terms/acronyms return the right paper: `LoRA` → LoRA paper at rank 1,
  `RAG` → RAG paper at rank 1 (both absent from dense top-5).
- Verified by `scripts/eval_search.py --check`.

### Task 2.3 - Corpus Expansion to ≥5k Papers

- **Assignee:** Saleh
- **Sequence:** S4
- **Priority:** High
- **Status:** ❌ Not built (corpus at ~500). Note: expansion path is now
  topic-snowball breadth (more topics / larger `--target`), not a NeurIPS venue add.

### Description:
- Extend ingest filter to add NeurIPS 2024 (one-parameter change per OD2). Re-embed and re-index Qdrant collection `axiom_v2` if schema changes.

### Acceptance Criteria:
- SQLite contains ≥5000 papers across ACL 2024-2025 + NeurIPS 2024.
- Qdrant index rebuilt; `search()` p95 <2s on 5k corpus.
- README documents corpus filter parameters.

### Task 2.4 - PDF Extract for Abstract+Intro Chunks (P3+)

- **Assignee:** Saleh
- **Sequence:** S5
- **Priority:** Medium
- **Status:** ❌ Not built.

### Description:
- Implement `ingest/pdf_extract.py` using Marker or PyMuPDF on demand via DOI; store intro text hash in provenance; never redistribute PDFs.

### Acceptance Criteria:
- `python -m ingest.pdf_extract --paper-id <id>` extracts intro markdown for a paper with resolvable DOI.
- `has_fulltext=true` set in provenance; PDF deleted after extraction.
- Failures logged; paper remains abstract-only without blocking pipeline.

---

## PBI 3 - Research Trends Extraction

**Status: ❌ NOT built.** No velocity engine and no keyword canonicalization exist.
This is the "trends" half of the product goal and remains the top forward-looking
gap (the citation years needed to compute velocity are already stored).

### User Story:
As a thesis-seeking researcher, I want to see which concepts are **accelerating** in my subfield, so that I understand what the field is doing without reading thousands of papers.

### PBI Acceptance Criteria:
- Velocity $v_k(t)$ computed with normalized frequency and log-ratio per PROJECT_PLAN §7.2.
- LLM keyword canonicalization merges synonyms (e.g. LoRA / Low-Rank Adaptation).
- `get_top_velocity_keywords(n, filters)` returns ≥50 keywords in <2s with confidence warning when $f_k < 5$.
- Trending data feeds Keyword Graph (≤50 nodes) without hairball overload.

### Task 3.1 - Velocity Engine

- **Assignee:** Yahor
- **Sequence:** Y3
- **Priority:** High
- **Status:** ❌ Not built.

### Description:
- Implement `trends/velocity.py`: compute $v_k(t)$ across conference-year windows from SQLite keywords/concepts; persist to `KEYWORD` table; expose `get_top_velocity_keywords(n, venue, year_range)`.

### Acceptance Criteria:
- `get_top_velocity_keywords(50)` returns ranked keywords with velocity and frequency for ACL 2024 vs 2025.
- Low-volume terms flagged with confidence warning in return payload.
- Computation <2s on 1k corpus, <5s on 5k.

### Task 3.2 - LLM Keyword Canonicalization

- **Assignee:** Yahor
- **Sequence:** Y4
- **Priority:** Medium
- **Status:** ❌ Not built.

### Description:
- Implement `trends/canonicalize.py`: batch 50 OpenAlex concept labels → LLM merge synonyms → persist canonical forms in `KEYWORD` table.

### Acceptance Criteria:
- Known synonym pairs (LoRA / Low-Rank Adaptation) map to single canonical entry.
- Canonicalization is idempotent; manual override table supported.
- No freestanding LLM claims - only label merging with logged inputs.

---

## PBI 4 - Citation Graph & Research-Gap Detection (OD9)

**Status: ⚠️ built, gap model diverged.** The NetworkX graph + PageRank is done
(T4.1). The gap detector is built but as the **OD9 community-pair** model, not the
original `s_max` + Scenario A/B pipeline. Neo4j (T4.3/T4.4) is dropped (OD6).

### User Story:
As a thesis-seeking researcher, I want to see sub-topics that are **related in
meaning but disconnected by citation**, so that I can spot bridges nobody has built
yet as candidate research directions.

### PBI Acceptance Criteria (as-built, OD9):
- NetworkX digraph built from SQLite `citation_edges`; PageRank influence on the
  corpus-only subgraph (OD8).
- Gap detection = Louvain communities → TF-IDF-distinctive concept labels →
  SPECTER2 centroid per community → score community **pairs**
  `gap_score = centroid_cosine / (1 + inter_community_citations)`.
- Results are framed as **candidate** gaps, never "proven"; honest caveat that on a
  sparse single-topic corpus the signal is weak (centroid cosines ~0.95).

> **Original plan (superseded):** a hypothesis-input gap evaluator — Step 1
> geometric void (`s_max`), Step 2 Scenario A (Dead End) / B (Fertile Frontier) via
> citation-path queries returning evidence IDs, with a Neo4j Cypher backend and a
> mandatory `disclaimer: Unverified Candidate`. Replaced by the corpus-level OD9
> detector; the hypothesis-evaluation + HITL flow is deferred to PBI 5.

### Task 4.1 - NetworkX Citation Graph Builder

- **Assignee:** Yahor
- **Sequence:** Y5
- **Priority:** High
- **Status:** ✅ Built (`axiom/graph.py`): DiGraph from `citation_edges`, corpus
  subgraph, neighbors, PageRank influence (pure-Python power iteration, no scipy),
  small drawable subgraphs. OD8.

### Description:
- Implement `graph/citation_graph.py`: load edges from SQLite, build `networkx.DiGraph`, expose neighbor queries and border-paper helpers for gap Step 2.

### Acceptance Criteria:
- Graph builds ≥1000 nodes / ≥5000 edges on 1k corpus in <60s.
- `get_neighbors(paper_id)` correct for a known hub paper.
- Rebuildable from SQLite on demand.

### Task 4.2 - Research-Gap Detector (OD9)

- **Assignee:** Yahor
- **Sequence:** Y6
- **Priority:** High
- **Status:** ✅ Built as OD9 (supersedes the s_max/Scenario-A-B design).

### Description (as-built, OD9):
- Implemented `axiom/gaps.py`: Louvain community detection on the undirected
  corpus citation graph → sub-topics; label each community by its most
  *distinctive* OpenAlex concepts (TF-IDF across communities); SPECTER2 centroid
  per community (via new `AxiomQdrant.fetch_dense_vectors()`); rank community
  **pairs** by `gap_score = centroid_cosine / (1 + inter_community_citations)`.
  NetworkX + numpy only (no scipy/torch).

### Acceptance Criteria:
- Detector returns ranked candidate community pairs with labels, centroid cosine,
  and inter-community citation count.
- First real run (500-paper RAG corpus): 12 interpretable communities; plausible
  candidates (e.g. aviation-maintenance RAG ⟷ telecom RAG, 0 inter-citations).
- Output framed as candidate gaps with the sparse-corpus caveat, never "proven".

> **Original plan (superseded):** `gap/evaluate.py` Steps 1–2 — Step 1 `s_max` via
> Qdrant, Step 2 Scenario A/B NetworkX path queries returning `GapResult`
> (verdict enum, evidence IDs, τ=0.65 "uncalibrated"). Deferred with PBI 5.

### Task 4.3 - ~~Neo4j Docker + Data Load~~ — DROPPED (OD6)

- **Assignee:** Saleh
- **Sequence:** S6
- **Priority:** ~~High~~ n/a
- **Status:** ❌ Dropped. Per **OD6** the graph store is NetworkX-first; SQLite
  `citation_edges` remains the durable edge source of truth. Revisit a dedicated
  graph DB only if NetworkX becomes a bottleneck. Original description retained
  below for reference.

### Description (superseded):
- Add Neo4j to `docker-compose.yml`; implement `graph/neo4j_loader.py` to load Paper nodes and CITES edges from SQLite per PROJECT_PLAN §6.2.

### Task 4.4 - ~~Gap Step 2 Neo4j Cypher~~ — DROPPED (OD6)

- **Assignee:** Saleh
- **Sequence:** S7
- **Priority:** ~~High~~ n/a
- **Status:** ❌ Dropped with T4.3 (NetworkX-first, OD6). Original description
  retained below for reference.

### Description (superseded):
- Port Scenario A and Scenario B to Cypher templates from PROJECT_PLAN §7.3; wire into `evaluate_gap()` behind same API contract; deprecate NetworkX path when Neo4j available.

---

## PBI 5 - LangGraph Agents & Gap Step 3

**Status: ❌ NOT built.** No LLM is in the pipeline yet — no LangGraph agents,
hypothesis generation, Verifier, composite G-score, `summarize_paper()`, or HITL
`review_queue`. This was the original product centerpiece (grounded hypothesis
pitch with supporting papers). It is **deferred pending the OD9 direction**: the
current gap detector is corpus-level (community pairs), not a per-hypothesis
evaluator, so the hypothesis + HITL flow needs a design pass before build.

### User Story:
As a researcher with a citation-verified frontier, I want a grounded hypothesis pitch with supporting papers, so that I can evaluate a concrete thesis direction - not a hallucinated trend.

### PBI Acceptance Criteria:
- LangGraph 5-node graph: Ingest_Summarizer, Trend_Aggregator, Gap_Narrator, Hypothesis_Generator, Verifier.
- Step 3 triggers only when Step 2 verdict = fertile_frontier.
- Verifier requires ≥2 `supporting_paper_ids`; empty lists retry ≤3×; temperature ≤0.3.
- Composite gap score $G$ computed and returned for ranked frontier candidates.
- HITL review queue backend stores candidates for human approval.

### Task 5.1 - LangGraph 5-Node Agent Graph

- **Assignee:** Yahor
- **Sequence:** Y7
- **Priority:** High
- **Status:** ❌ Not built (deferred, see PBI 5 status).

### Description:
- Implement `agents/graph.py` and `agents/nodes/`: stateful LangGraph with nodes per PROJECT_PLAN §7.3; structured Pydantic outputs at each boundary; max 3 Verifier retries.

### Acceptance Criteria:
- Graph runs end-to-end for a frontier `h_syn` on demo corpus.
- `Hypothesis_Generator` returns JSON: title, claim, method_sketch, datasets, `supporting_paper_ids`.
- Verifier rejects outputs with <2 supporting IDs and retries.
- `summarize_paper()` produces 3-bullet abstract summary with `paper_id` cites.

### Task 5.2 - Gap Step 3, G Scoring & HITL Queue

- **Assignee:** Yahor
- **Sequence:** Y8
- **Priority:** High
- **Status:** ❌ Not built (deferred, see PBI 5 status).

### Description:
- Wire Step 3 into `evaluate_gap()` / `generate_hypothesis()`; implement `gap/scoring.py` for composite $G$; add SQLite `review_queue` table for HITL candidates with status (pending / approved / rejected).

### Acceptance Criteria:
- Full `evaluate_gap()` returns Steps 1-3 when verdict=frontier; Steps 1-2 only when dead_end.
- $G$ score returned with weight breakdown per PROJECT_PLAN §7.3 defaults.
- Review queue API: list pending, approve, reject - no candidate promoted without human action.
- Full 3-step pipeline <10s on 1k corpus (LLM latency excluded from hard fail; log p95).

---

## PBI 6 - FastAPI Service Layer

**Status: ❌ NOT built.** No `api/`. Streamlit imports the `axiom/*` modules
directly. This is the stable seam React will need — build it before any React work.

### User Story:
As a frontend developer, I want a stable REST API over all backend modules, so that React pages consume one contract instead of importing Python modules directly.

### PBI Acceptance Criteria:
- FastAPI app exposes search, trends, gap evaluation, reading list, and review queue endpoints.
- OpenAPI docs generated at `/docs`.
- CORS configured for local React dev; env-driven config; no secrets in repo.

### Task 6.1 - FastAPI Core Routes

- **Assignee:** Yahor
- **Sequence:** Y9
- **Priority:** High
- **Status:** ❌ Not built.

### Description:
- Implement `api/main.py`: REST wrappers for `search`, `get_top_velocity_keywords`, `evaluate_gap`, `generate_hypothesis`, `summarize_paper`, reading list CRUD, review queue CRUD. Pydantic request/response models mirror `contracts/`.

### Acceptance Criteria:
- `uvicorn api.main:app` starts; `/docs` lists all endpoints.
- `POST /gap/evaluate` returns full 3-step result for frontier demo example from `docs/demo_examples.md`.
- `GET /trends/top?n=50` returns velocity table in <2s.
- `POST /reading-list/{paper_id}/summarize` returns 3 bullets each citing `paper_id`.
- Integration smoke test script passes against docker-compose stack.

---

## PBI 7 - Discovery Dashboard

**Status: ⚠️ partial, Streamlit only.** Built: a **Search** view and a **Citation
graph** view (3D force-directed viz + OD9 Research-gaps view). Not built: Trending
Topics, Gap Evaluator (3-step badges/HITL), Reading List, and the React migration.
The graph UX is **3D** by design (the original "no 3D" scope line is reversed — see
Out of Scope).

### User Story:
As a mentor or researcher, I want a polished four-page dashboard to explore trends and gaps with honest limitation badges, so that the LLMs for Sciences vision is tangible in one click-through.

### PBI Acceptance Criteria:
- All four PROJECT_PLAN §8 pages implemented in React (Streamlit used for early dev only).
- **Trending Topics**: velocity list, venue/year filters, sparklines.
- **Keyword Graph**: force-directed, ≤50 nodes, size=citation weight, color=velocity, renders <3s.
- **Gap Evaluator**: 3 steps, badges, mini citation diagram, $G$ breakdown, HITL queue UI, Unverified Candidate banner.
- **Reading List**: bookmarks, 3-bullet cited summaries.
- No 3D/WebGL; no cluster hairball as hero UX.

### Task 7.1 - Trending Topics Page

- **Assignee:** Yakub
- **Sequence:** K2
- **Priority:** High
- **Status:** ❌ Not built (blocked on the velocity engine, T3.1).

### Description:
- Build Trending page in Streamlit first, migrate to React (Stitch export): velocity-ranked table, venue/year filters, sparklines, low-volume warnings.

### Acceptance Criteria:
- Top-50 keywords with velocity load <2s via FastAPI.
- Filters reduce results correctly.
- React page matches Stitch wireframe at functional level.

### Task 7.2 - Citation Graph Page (3D)

- **Assignee:** Yakub
- **Sequence:** K3
- **Priority:** High
- **Status:** ✅ Built (as a 3D citation graph, supersedes the 2D keyword graph).

### Description (as-built):
- Interactive **3D force-directed** citation graph (`3d-force-graph`, WebGL/three.js
  via CDN, embedded with `st.components.v1.html`). Two views: **Top influential**
  (top-N PageRank subgraph) and **Around a paper** (1-hop ego network). Node size =
  in-degree within the view; gold particles flow citing→cited; click to fly the
  camera. A **Research-gaps** view colours nodes by OD9 community and renders the
  two related-but-disconnected clusters for a picked candidate. Accessibility pass:
  legend, contrast, and a "Show 3D graph" toggle (scroll-trap escape hatch).

> **Original plan (superseded):** a 2D force-directed **keyword** graph, ≤50 nodes,
> node size = citation weight, colour = velocity. Replaced by the 3D citation graph;
> a velocity-coloured keyword graph is deferred with the velocity engine (T3.1).

### Acceptance Criteria:
- Renders both views on the 500-paper corpus; no black-canvas/blank failures.
- Click a node → detail (DOI, local vs global citations, top citing papers).

### Task 7.3 - Gap Evaluator Page

- **Assignee:** Yakub
- **Sequence:** K4
- **Priority:** High
- **Status:** ⚠️ Partial. The OD9 **Research-gaps** view (candidate community-pair
  picker + "why this is a gap" explainer + ranked list) is built inside the Citation
  graph tab. The original 3-step UI (h_syn input, s_max void map, Dead End/Frontier
  badges, Step-3 hypothesis pitch + G breakdown, HITL review queue, non-suppressable
  "Unverified Candidate" banner) is **not** built — deferred with PBI 5.

### Description:
- Full 3-step UI: `h_syn` input, Step 1 void map + `s_max`, Step 2 badge (Dead End / Fertile Frontier) + citation evidence, Step 3 hypothesis pitch + $G$ breakdown. HITL review queue panel. Non-suppressable Unverified Candidate banner.

### Acceptance Criteria:
- Demo Frontier and Dead End examples from `docs/demo_examples.md` render correct badges.
- Step 3 shows `supporting_paper_ids` as clickable paper links.
- User can approve/reject frontier candidates in review queue.
- Copy: "candidate directions, not validated gaps" visible on every evaluation.

### Task 7.4 - Reading List Page

- **Assignee:** Yakub
- **Sequence:** K5
- **Priority:** High
- **Status:** ❌ Not built (depends on `summarize_paper()`, T5.1).

### Description:
- Bookmark papers from search or gap results; display 3-bullet LLM summaries via FastAPI; all bullets must show `paper_id` citation.

### Acceptance Criteria:
- Add/remove bookmarks persists across sessions (local storage or backend).
- Every summary bullet links to source paper; empty unsupported claims rejected by API surface as error.
- Page loads in <3s for 20 bookmarked papers.

---

## PBI 8 - Evaluation, Calibration & Scale

**Status: ⚠️ minimal.** A search-quality harness exists (`scripts/eval_search.py`:
raw vs expansion vs hybrid + acceptance checks). No nDCG@10, no threshold
calibration (τ is n/a — the s_max/verdict model was dropped), no gap-quality study,
no `demo_examples.md` / slide package.

### User Story:
As a team presenting to mentors, we want measured quality metrics and a reproducible runbook, so that trends and gaps claims are backed by data - not vibes.

### PBI Acceptance Criteria:
- τ, $\delta_D$, $\delta_F$ calibrated per PROJECT_PLAN §7.3 protocol (20 established + 10 dead + 10 hot topics).
- nDCG@10 ≥0.65 on 20 hand-labeled queries.
- Gap quality mean ≥3.0 on rated candidates; Dead End / Frontier accuracy ≥70% on 20 labeled voids.
- README runbook: clone → compose up → ingest → index → demo in documented steps.
- Total embedding + LLM cost for 5k papers documented as <$5.

### Task 8.1 - Threshold Calibration Notebook

- **Assignee:** Yahor
- **Sequence:** Y10
- **Priority:** High
- **Status:** ❌ Not built. τ/δ calibration was tied to the dropped s_max/Scenario
  model; if OD9 stays, calibration would instead target the `gap_score` threshold.

### Description:
- Implement `eval/calibration.ipynb`: labeled mini-set, precision/recall curves for τ, $\delta_D$, $\delta_F$; export chosen thresholds to config file consumed by `gap/evaluate.py`.

### Acceptance Criteria:
- Notebook runs end-to-end on 5k corpus with committed labeled set in `eval/labels/`.
- Selected τ documented with precision/recall at operating point.
- `evaluate_gap()` reads calibrated thresholds from config (overrides dev default 0.65).

### Task 8.2 - Retrieval & Gap Quality Evaluation

- **Assignee:** All
- **Sequence:** A1
- **Priority:** High
- **Status:** ⚠️ Partial. `scripts/eval_search.py` compares retrieval modes and
  asserts acceptance checks (e.g. LoRA/RAG top-1), but there is no labeled nDCG@10
  set, no `eval/` dir, and no gap-quality rating study yet.

### Description:
- Create `eval/ndcg_queries.json` (20 queries, 2 annotators); run nDCG@10 on search results. Rate 10 gap candidates 1-5 (team + volunteers). Measure Dead End / Frontier accuracy on 20 labeled voids.

### Acceptance Criteria:
- nDCG@10 ≥0.65 reported in `eval/report.md`.
- Gap quality mean ≥3.0; classification accuracy ≥70% on labeled void set.
- Search p95 <2s and gap eval p95 <10s on 5k corpus logged.

### Task 8.3 - Runbook, Demo Package & Final Report

- **Assignee:** All
- **Sequence:** A2
- **Priority:** High
- **Status:** ⚠️ Partial. `README.md` + `docs/WALKTHROUGH.md` + `docs/21-06.md`
  cover the current run path; no `docs/demo_examples.md` and no mentor slide package.

### Description:
- README runbook (clone → install → compose → ingest → embed → index → migrate neo4j → start API → start React). `docs/demo_examples.md` with 2 gap examples + trending highlights. Mentor slides: **LLMs for Sciences: Research Trends & Gaps Extraction Tool** with architecture diagram and limitations.

### Acceptance Criteria:
- Fresh machine can follow README to running demo without undocumented steps.
- `docs/demo_examples.md` reproducible on demo DB.
- Slides include screenshots of all 4 pages with HITL badges visible.
- Limitations section: corpus scope, calibrated vs uncalibrated periods, hallucination controls, English-only.

---

## Out of Scope

- ~~3D WebGL / Three.js visualization~~ — **reversed (2026-06-21).** A 3D
  force-directed graph (`3d-force-graph`) is now the hero graph UX; a flat 2D
  attempt was an unreadable hairball. The *hairball* rejection still holds — 3D
  gives a rotatable/zoomable node-link view, not a cluster blob. (work log §5, T7.2)
- 2D topic-cluster hairball as primary UX (rejected per mentor feedback) — still out
- Neo4j / dedicated graph DB (NetworkX-first per OD6; revisit only if it bottlenecks)
- Reuse or migration of prior POC codebases
- LLM model training or fine-tuning
- Production SLA, multi-language support, social features

---

## Known Risks & Mitigations

- **OpenAlex abstracts missing on ~15-20% of papers.** Title-only embed with flag; exclude from gap scoring; show "limited text" in UI.
- **Neo4j is new ops for the team.** ✅ *Resolved:* staying NetworkX-first (OD6);
  Neo4j dropped. SQLite `citation_edges` is the durable edge source; revisit a graph
  DB only if NetworkX bottlenecks.
- **LangGraph Step 3 can sprawl.** *Not yet built (PBI 5, deferred).* When built:
  hard cap 5 nodes, 3 Verifier retries, Pydantic at every boundary; no extra agent
  nodes without a DECISIONS entry.
- **τ wrong until PBI 8 lands.** *Moot for now:* the s_max/verdict model that τ
  calibrated was dropped (OD9). If OD9 stays, calibrate the `gap_score` threshold
  instead; current gap output is labeled a **candidate** with a sparse-corpus caveat.
- **Hallucinated hypothesis pitches.** *Not yet applicable* — no LLM hypothesis
  generation is built. The design (Verifier enforces `supporting_paper_ids`, empty →
  retry, HITL blocks auto-promotion) carries into PBI 5 when built.
- **Sparse single-topic corpus weakens OD9 gaps.** Centroid cosines cluster tightly
  (~0.95) and most community pairs have 0 inter-citations. Mitigate with denser /
  multi-topic corpora (T2.3) and label candidates honestly.
- **React/Stitch migration friction.** Streamlit hosts working demo until each React page replaces it; API (PBI 6) is the stable seam.
- **5k embed + index runtime.** Batch embeddings with hash skip; versioned Qdrant collections (`axiom_v1` → `axiom_v2`); document GPU path in README.
- **Saleh and Yakub blocked on interface changes.** Yahor owns `contracts/`; signature changes discussed in standup before merge, not mid-sprint via silent PR.

---

## Cross-Task Dependency Hints

- T1.1 (scaffold + contracts) blocks all other tasks - mocks unblock parallel UI and ingest work.
- T1.2 (ingest) blocks T2.1, T3.1, T4.1 - no embeddings, trends, or graph without papers.
- T2.1 → T2.2 (embed before Qdrant) → T2.3 (scale after base index works).
- T3.1 (velocity) blocks T7.1 and T7.2; T3.2 (canonicalization) improves T7.1 quality but is not blocking.
- T4.1 (NetworkX) → T4.2 (OD9 gap detector). ~~T4.3/T4.4 (Neo4j)~~ dropped (OD6).
- T4.2 + T3.1 would block T5.1 (LangGraph needs a gap signal + trend context) — both
  the velocity engine and the LLM pipeline are still unbuilt.
- T5.1 blocks T5.2 and T7.4 (summaries); T5.2 blocks T7.3 (full gap UI).
- T6.1 (FastAPI) should land before React pages T7.1-T7.4; Streamlit can call Python modules directly until then.
- T2.3 (5k corpus) should complete before T8.1/T8.2 eval; T8.1 calibration before final threshold claims in T8.3.
- T7.3 (Gap Evaluator) and T8.2 (eval) should precede T8.3 (demo package) so screenshots and metrics are real.

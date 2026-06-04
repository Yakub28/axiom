# Axiom P1 — Complete Walkthrough

This document is a full, self-contained explanation of the **P1 data-foundation
seam**: what it is, why each piece exists, how the data flows, how to run it, and
how it was verified with a real end-to-end run. Read it top-to-bottom and you
should understand every file in the repo and be able to reproduce the demo.

- **Audience:** anyone on the Axiom team (UI, data, graph) plus future-you.
- **Status:** built and verified on 2026-06-04 (real SPECTER2 run, see §9).
- **Scope:** P1 only. Velocity engine, citation graph, gap pipeline, React, and
  FastAPI are explicitly *not* here — see §11 for where they plug in later.

---

## 1. What Axiom is (and what it is not)

**Axiom is a thesis-discovery tool for researchers.** Its purpose is to surface
*what is trending* in a subfield and *what conceptual space is unexplored* — i.e.
to help a researcher find a thesis-worthy gap.

It is **not** a paper search engine. Semantic search over papers (what P1 builds)
is the *foundation* the later trend/gap features stand on, not the product itself.

**P1 — the "data-foundation seam"** — is the minimum that lets the UI track work
end-to-end before real ingestion and the production encoder exist:

1. A SQLite schema that is the **shared data contract** for the whole team.
2. A local **Qdrant** vector store (via Docker) + a Python client wrapper.
3. A **SPECTER2** abstract encoder (768-dim) with a CPU fallback.
4. A **bootstrap** that loads a synthetic 30-paper corpus so the UI runs today.
5. One **Streamlit** page: semantic search box + venue/year filter bar.

---

## 2. Architecture & data flow

```
                          ┌──────────────────────────────────────┐
   OpenAlex  (P2, not yet) │   db/schema.sql                       │
        │                  │   THE SHARED DATA CONTRACT            │
        │ ingestion (P2)   │   papers · concepts · citation_edges  │
        ▼                  │          · paper_provenance           │
  ┌───────────────┐        └──────────────────────────────────────┘
  │ bootstrap_     │                    │ defines tables
  │ synthetic.py   │  writes rows       ▼
  │ (30 fake       ├───────────────►  SQLite  (data/axiom.db)
  │  NLP papers)   │                    │
  └──────┬─────────┘                    │ reads title+abstract, concepts
         │                              ▼
         │  per paper:           ┌─────────────────┐
         │  title [SEP] abstract │ axiom/embed.py  │  SPECTER2, 768-dim
         └──────────────────────►│ Specter2Encoder │  CLS pooling, GPU→CPU
                                 └────────┬────────┘
                                          │ 768-dim vectors + payload
                                          ▼
                                 ┌─────────────────────┐
                                 │ axiom/qdrant_client │  collection "axiom_v1"
                                 │ AxiomQdrant         │  1 point / paper
                                 │  upsert / search    │  payload: paper_id,title,
                                 └────────┬────────────┘  year,venue,cited_by,concepts
                                          │ dense vector + payload filter
                                          ▼
                                 ┌─────────────────────┐
                                 │ app/streamlit_app   │  query box + venue
                                 │                     │  multiselect + year slider
                                 └─────────────────────┘
```

**The two "contracts" everyone codes against** (frozen first, before anything
else was built):

1. `db/schema.sql` — the table/column names.
2. `AxiomQdrant.search(query_vector, top_k, venues, year_range) -> list[SearchHit]`.

Changing either ripples across tracks, so changes must be logged in
`docs/DECISIONS.md`.

---

## 3. The SQLite contract (`db/schema.sql`)

SQLite is the **durable source of truth** for paper metadata, concepts, and
citation edges. Qdrant holds only vectors + a denormalized payload for fast
filtering; if Qdrant is wiped, it can be fully rebuilt from SQLite.

### Tables

| Table | Purpose | Key columns |
|---|---|---|
| `papers` | one row per paper | `openalex_id` (PK), `title`, `abstract`, `publication_year`, `venue_id`, `venue`, `cited_by_count`, `doi` |
| `concepts` | many concepts per paper | `paper_id`, `concept`, `level` |
| `citation_edges` | citation graph edges (P2) | `src_id`, `dst_id`, `year` |
| `paper_provenance` | fetch bookkeeping | `paper_id` (PK), `source`, `fetched_at`, `text_hash`, `has_fulltext` |

### Design decisions baked into the schema

- **Abstracts are plain text here.** OpenAlex stores abstracts as an *inverted
  index* (`{word: [positions]}`). Ingestion (P2) must reconstruct them to plain
  text *before* inserting into `papers.abstract`. The encoder assumes plain text.
- **`citation_edges.dst_id` has no foreign key — on purpose.** A paper's
  `referenced_works[]` routinely cites papers outside the local corpus. Those
  "dangling" edges are exactly what the graph track needs, so the schema must not
  reject them. `src_id` *does* have an FK (the citing paper is always in-corpus).
- **Five read-path indexes** (`publication_year`, `venue`, `concepts.paper_id`,
  `citation_edges.src_id`, `citation_edges.dst_id`). These make the UI filter bar
  and the P2 graph reads index lookups instead of full scans. They are pure
  additions over the spec — nothing downstream breaks.
- **`text_hash`** (SHA-256 of the abstract) supports dedup / change-detection
  during real ingestion.

---

## 4. The search contract (`AxiomQdrant.search`)

```python
def search(
    query_vector: list[float],            # 768-dim SPECTER2 embedding of the query
    top_k: int = 10,
    venues: list[str] | None = None,      # payload filter: match ANY of these (OR)
    year_range: tuple[int, int] | None = None,  # inclusive (min, max) on payload.year
) -> list[SearchHit]:
    ...
```

```python
@dataclass
class SearchHit:
    paper_id: str
    title: str
    year: int
    venue: str
    cited_by_count: int
    score: float
    concepts: list[str]
```

**Why it takes a raw vector, not text.** The vector store stays decoupled from
the encoder. The Streamlit page owns the `encode → search` wiring, so the
embedding track and the vector track can evolve independently. (We can add a
text-accepting convenience later without breaking this.)

**Filter semantics:**
- Facets combine with **AND** (`Filter(must=[...])`).
- Within `venues`, matches are **OR** (`MatchAny`).
- `year_range` is an inclusive numeric `Range(gte, lte)` on `payload.year`.
- Filters are applied **natively by Qdrant**, not post-filtered in Python — so
  `top_k` is honored *after* filtering (you always get up to k matching hits).

**Why a typed `SearchHit`.** The Streamlit page never touches raw Qdrant
objects. If we swap vector stores later, only `qdrant_client.py` changes.

---

## 5. File-by-file

```
db/schema.sql                    Shared SQLite contract (see §3). Top comment says
                                 "changes must be logged in docs/DECISIONS.md".

axiom/config.py                  Single source of truth for constants:
                                 - DB_PATH, SCHEMA_PATH
                                 - QDRANT_HOST/PORT, COLLECTION_NAME = "axiom_v1"
                                 - MODEL_ID = "allenai/specter2_base", VECTOR_SIZE = 768
                                 - DEFAULT_TOP_K = 10
                                 Everything imports from here — no magic strings.

axiom/db.py                      SQLite access layer. All SQL lives here:
                                 connect() (FK on, Row factory), init_db()
                                 (runs schema.sql), insert_paper/concepts/
                                 citation_edges/provenance, text_hash(),
                                 distinct_venues(), year_bounds(), iter_papers().
                                 TODO(P2): OpenAlex ingestion plugs in here.

axiom/embed.py                   Specter2Encoder. Loads allenai/specter2_base via
                                 transformers. encode() builds "title [SEP] abstract"
                                 and takes the [CLS] token of the last hidden state
                                 (the canonical SPECTER recipe). Batched. Device
                                 pick order: CUDA > Apple MPS > CPU; on CPU it WARNS
                                 (never silently swaps models). encode_query() does
                                 a single free-text string.
                                 TODO(P2): load the SPECTER2 proximity adapter.

axiom/qdrant_client.py           AxiomQdrant wrapper (see §4). Owns collection
                                 lifecycle (recreate_collection — used for the
                                 idempotent bootstrap), upsert_papers(), count(),
                                 and search(). Defines SearchHit.
                                 (File is named qdrant_client.py to match the spec;
                                 Python 3 absolute imports still resolve
                                 `from qdrant_client import QdrantClient` to the
                                 installed package, not this module.)

scripts/bootstrap_synthetic.py   The 30-paper synthetic corpus (inline data) plus
                                 load_sqlite() and load_qdrant(). IDEMPOTENT:
                                 deletes prior rows and recreates the Qdrant
                                 collection on every run. See §6.

app/streamlit_app.py             The UI. See §8.

docker-compose.yml               Qdrant service only (image qdrant/qdrant:v1.9.0,
                                 ports 6333/6334, named volume for storage).

requirements.txt                 Pinned, minimal: torch, transformers,
                                 qdrant-client, streamlit, pandas, numpy, tqdm.

docs/DECISIONS.md                Committed decisions + the schema change log.
docs/WALKTHROUGH.md              This file.
README.md                        Quick run order + the 5 demo queries.
```

> Note: `qdrant/populate_qdrant.py` is a **separate earlier experiment** from
> another teammate (different model `all-MiniLM-L6-v2`, 384-dim, collection
> `academic_papers`). It is **not** part of the P1 seam and is left untouched.

---

## 6. The synthetic corpus & why it's idempotent

`scripts/bootstrap_synthetic.py` contains 30 hand-written, plausible ACL-style
NLP papers (`S0001`–`S0030`) spanning **2021–2025** across venues
`ACL / EMNLP / NeurIPS / ICLR / NAACL`, grouped into coherent topics so that
nearest-neighbor results are visibly sensible:

| Topic | Papers |
|---|---|
| Retrieval-Augmented Generation | S0001–S0004 |
| LoRA / PEFT | S0005–S0008 |
| Low-resource & multilingual | S0009–S0012 |
| Evaluation | S0013–S0014 |
| Instruction tuning / alignment | S0015–S0017 |
| Hallucination / factuality | S0018–S0019 |
| Long context | S0020–S0021 |
| Prompting / reasoning | S0022–S0024 |
| Distillation / efficiency | S0025–S0026 |
| Embeddings / retrieval models | S0027–S0030 |

Each paper carries a realistic abstract, concept list (with levels), a
`cited_by_count`, and a synthetic `references` list that becomes
`citation_edges` rows (so the P2 graph track has real-shaped data to build on).

**Two stages, both idempotent:**

1. `load_sqlite()` — `init_db()` (creates tables if absent), then `DELETE FROM`
   each table, then re-insert all 30 papers + concepts + edges + provenance.
2. `load_qdrant()` — reads papers + concepts back from SQLite, encodes
   `title [SEP] abstract` with SPECTER2, then `recreate_collection()` (drops &
   recreates `axiom_v1`) and upserts 30 points with the payload
   `{paper_id, title, year, venue, cited_by_count, concepts}`.

Because both stages wipe-then-write, you can run the script as many times as you
like and always land in the same clean state.

---

## 7. How to run it

### Prerequisites
- **Docker** (for Qdrant).
- **Python 3.10–3.12.** ⚠️ Not 3.13/3.14 — the pinned `torch`/`transformers`
  have no wheels there. (See §10 for the gotcha we hit on this machine.)

### Steps (from the repo root)

```bash
# 1. Create a venv on a supported Python and install the pinned stack
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# 2. Start Qdrant
docker compose up -d

# 3. Load the synthetic corpus into SQLite + Qdrant (idempotent;
#    first run downloads SPECTER2 weights, ~440 MB)
python scripts/bootstrap_synthetic.py

# 4. Launch the search UI
streamlit run app/streamlit_app.py
```

Expected bootstrap output:

```
[sqlite] wrote 30 papers to .../data/axiom.db
[embed] loading allenai/specter2_base (first run downloads weights)...
[embed] encoding 30 abstracts on device=mps      # or cuda / cpu
[qdrant] recreating collection 'axiom_v1'...
[qdrant] upserted 30 points into 'axiom_v1'
Bootstrap complete. Run:  streamlit run app/streamlit_app.py
```

### Five demo queries (also in the README)

Type these into the search box; each returns intuitively relevant papers:

1. `reducing hallucination in retrieval-augmented generation`
2. `parameter efficient fine-tuning with low-rank adapters`
3. `low-resource machine translation with limited parallel data`
4. `evaluating language models beyond accuracy`
5. `chain-of-thought reasoning and self-consistency`

Then exercise the filter bar: restrict **Venue** to `ICLR`, or drag the **Year
range** to 2024–2025, and watch the result set change.

---

## 8. How the Streamlit page works

`app/streamlit_app.py`, top to bottom:

1. **Cached singletons** (`@st.cache_resource`) for the SPECTER2 encoder and the
   `AxiomQdrant` client, so they're built once per session, not per keystroke.
   `@st.cache_data` caches the filter options (venue list + year bounds) read
   from SQLite.
2. **Guard rails (no stack traces):**
   - If Qdrant is unreachable → a clear in-UI error telling you to run
     `docker compose up -d` and the bootstrap, then `st.stop()`.
   - If the index is empty (`count() == 0`) → a warning to run the bootstrap,
     then `st.stop()`.
3. **Filter bar:** a venue `multiselect` (options from SQLite), a year-range
   `slider` (bounds from SQLite), and a `Top-K` number input.
4. **Query flow:** on a non-empty query → `encoder.encode_query(query)` →
   `store.search(query_vector, top_k, venues, year_range)` → render hits as a
   pandas DataFrame (Score, Title, Year, Venue, Citations, Concepts).
   Empty filtered result → a friendly "loosen your filters" message.

The page never imports Qdrant types directly — it only sees `SearchHit`.

---

## 9. Verification — the real end-to-end run (2026-06-04)

The full pipeline was executed, not just unit-checked:

- **Bootstrap:** 30 papers written to SQLite (90 concept rows, 29 citation
  edges); SPECTER2 (`allenai/specter2_base`) encoded all 30 abstracts on **Apple
  MPS**; 30 points upserted into `axiom_v1`.
- **Streamlit:** boots headless and serves — `GET /` → HTTP 200,
  `/_stcore/health` → ok.

**The 5 demo queries (top-3 each, real embeddings):**

```
Q: reducing hallucination in retrieval-augmented generation
   0.941 [2023 EMNLP] Surveying Hallucination in Natural Language Generation
   0.929 [2023 ACL]   Self-Reflective Retrieval Augmentation Reduces Hallucination...
   0.925 [2021 NeurIPS] Retrieval-Augmented Generation for Knowledge-Intensive NLP

Q: parameter efficient fine-tuning with low-rank adapters
   0.934 [2025 EMNLP] Composable Adapters for Continual Instruction Tuning
   0.932 [2023 NeurIPS] QLoRA: Efficient Finetuning of Quantized Language Models
   0.932 [2024 ICLR]  Rank-Adaptive PEFT: Allocating Capacity Across Layers...

Q: low-resource machine translation with limited parallel data
   0.970 [2022 ACL]   Data Augmentation via Back-Translation for Low-Resource MT
   0.919 [2021 EMNLP] Cross-Lingual Transfer for Low-Resource NER
   0.910 [2023 NeurIPS] QLoRA: Efficient Finetuning of Quantized Language Models

Q: evaluating language models beyond accuracy
   0.970 [2022 NeurIPS] Beyond Accuracy: Holistic Evaluation of Language Models
   0.948 [2024 EMNLP] LLM-as-a-Judge: Reliability and Bias of Model-Based Evaluation
   0.931 [2022 NeurIPS] Training Language Models to Follow Instructions with...

Q: chain-of-thought reasoning and self-consistency
   0.940 [2023 ICLR]  Self-Consistency Improves Chain-of-Thought Reasoning
   0.924 [2022 NeurIPS] Chain-of-Thought Prompting Elicits Reasoning in LLMs
   0.918 [2025 ICLR]  Verifier-Guided Search for Reliable Multi-Step Reasoning
```

**Filters demonstrably change results** (same PEFT query):

```
venue = ICLR only        → surfaces the original "LoRA" (2021 ICLR) paper
year  = 2024–2025 only    → drops older NeurIPS/ICLR hits, returns only recent work
```

Each query's neighbors stay within its topic cluster, which is the signal that
the SPECTER2 embeddings are doing real semantic work — the P1 demo bar is met.

---

## 10. Environment gotcha (read this before you run)

This dev machine's **default `python3` is 3.14**, and the pinned
`torch==2.2.2` / `transformers==4.40.2` have **no wheels for 3.14** (torch only
ships ≥2.9 there). The fix applied here:

```bash
brew install python@3.12          # -> /opt/homebrew/bin/python3.12 (3.12.13)
/opt/homebrew/bin/python3.12 -m venv .venv
. .venv/bin/activate              # IMPORTANT: bare python3 is still 3.14
pip install -r requirements.txt
```

`requirements.txt` is intentionally left pinned at the team-committed versions
(correct for any supported 3.10–3.12). Don't bump them just to run on 3.14 — that
would silently change a committed decision.

---

## 11. P2 seams (where the next tracks plug in)

Marked in code with `# TODO(P2)` — interfaces only, no implementation:

| Seam | Location | What plugs in |
|---|---|---|
| **Ingestion** | `axiom/db.py` (bottom) | Replace synthetic loading with OpenAlex fetch + inverted-index abstract reconstruction, writing through the same `insert_*` helpers so the contract is unchanged. |
| **Better embeddings** | `axiom/embed.py` (`__init__`) | Load the SPECTER2 proximity adapter for higher-quality neighbors (needs `adapter-transformers`). |
| **Velocity + citation graph** | `axiom/qdrant_client.py` (bottom) | These tracks read the same payload fields (`year`, `concepts`, `cited_by_count`) to rank trending work and detected gaps. The `citation_edges` table is already populated for a NetworkX-first graph (decision **OD6** — no Neo4j in P1/P2). |

**Explicitly out of scope for P1:** velocity engine, citation graph, LangGraph,
gap pipeline, React, FastAPI. Don't build them yet.

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| UI: "Cannot reach Qdrant" | `docker compose up -d`, wait a few seconds, then run the bootstrap. |
| UI: "The index is empty" | `python scripts/bootstrap_synthetic.py`. |
| `No matching distribution found for torch==2.2.2` | You're on Python 3.13/3.14. Use a 3.10–3.12 venv (see §10). |
| First encode is slow | Expected on CPU; weights download once and are cached. A GPU/MPS path is used automatically when available. |
| Want a clean reset | Re-run the bootstrap (idempotent), or `docker compose down -v` to also drop the Qdrant volume. |

---

## 13. One-line summary

P1 gives the team a frozen SQLite contract, a Qdrant-backed SPECTER2 semantic
search over a synthetic 30-paper corpus, and a working Streamlit search page —
so the UI track is unblocked today and the data/graph tracks have stable seams to
build the real trend/gap product on.

# Axiom

**Thesis-discovery tool for researchers.** Axiom is *not* a paper search engine —
it surfaces what's trending in a subfield and what conceptual space is unexplored.

This repo currently contains the **P1 data-foundation seam**: a shared SQLite
contract, a local Qdrant vector store, a SPECTER2 encoder, a synthetic 30-paper
bootstrap, and a Streamlit search page. It runs end-to-end against synthetic data
so the UI is unblocked before real ingestion and the production encoder land.

> Out of scope in P1 (do not expect them here): velocity engine, citation graph,
> LangGraph, gap pipeline, React, FastAPI. Interface seams are marked
> `# TODO(P2)`.

---

## Run order (exact commands)

From the repo root:

```bash
# 1. Install deps (a virtualenv is recommended)
pip install -r requirements.txt

# 2. Start Qdrant (Docker)
docker compose up -d

# 3. Load the synthetic corpus into SQLite + Qdrant (idempotent)
python scripts/bootstrap_synthetic.py

# 4. Launch the search UI
streamlit run app/streamlit_app.py
```

Step 3 is safe to re-run: it wipes and recreates the `axiom_v1` collection and
rewrites the SQLite rows.

> First run of step 3 downloads the `allenai/specter2_base` weights (~440 MB).
> With no GPU it runs on CPU and prints a warning — the model is unchanged.

---

## Five demo queries

Type these into the search box; each should return intuitively relevant papers:

1. `reducing hallucination in retrieval-augmented generation`
2. `parameter efficient fine-tuning with low-rank adapters`
3. `low-resource machine translation with limited parallel data`
4. `evaluating language models beyond accuracy`
5. `chain-of-thought reasoning and self-consistency`

Then exercise the filter bar: restrict **Venue** to e.g. `ACL` + `EMNLP`, or
drag the **Year range** to 2024–2025, and watch the result set change.

---

## Architecture (P1)

```
OpenAlex (P2)            db/schema.sql  ← shared data contract (the team codes against this)
     │                        │
     ▼                        ▼
scripts/bootstrap_synthetic.py ──► SQLite (data/axiom.db)
     │                                  │
     │  SPECTER2 (axiom/embed.py)       │ papers · concepts · citation_edges · provenance
     ▼                                  ▼
  768-dim vectors ──► Qdrant `axiom_v1` (axiom/qdrant_client.py)
                              │
                              ▼
                   app/streamlit_app.py  (search box + venue/year filters)
```

- **Data contract:** `db/schema.sql`. Schema changes must be logged in
  `docs/DECISIONS.md`.
- **Embeddings:** SPECTER2 (`allenai/specter2_base`, 768-dim), CLS pooling over
  `title [SEP] abstract`; GPU → CPU fallback with a warning.
- **Vector store:** Qdrant, one point per paper, payload
  `paper_id, title, year, venue, cited_by_count, concepts[]`; hybrid search =
  dense vector + payload filter on `venue`/`year`.
- **Graph store:** NetworkX-first (decision OD6). The `citation_edges` table
  already exists for the P2 graph track.
- **Frontend:** Streamlit.

---

## Layout

```
db/schema.sql                    shared SQLite contract
axiom/config.py                  paths, Qdrant host/port, collection, model id
axiom/db.py                      SQLite connect/init/insert helpers
axiom/embed.py                   SPECTER2 encoder (GPU→CPU fallback)
axiom/qdrant_client.py           collection lifecycle, upsert, search-with-filter
scripts/bootstrap_synthetic.py   30 synthetic NLP papers → SQLite + Qdrant
app/streamlit_app.py             search page + filter bar
docker-compose.yml               qdrant service only
docs/DECISIONS.md                committed decisions + schema change log
```

> `qdrant/populate_qdrant.py` is a separate earlier experiment (different model
> and collection) and is **not** part of the P1 seam.

---

## Troubleshooting

- **"Cannot reach Qdrant" in the UI** → run `docker compose up -d`, wait a few
  seconds, then `python scripts/bootstrap_synthetic.py`.
- **"The index is empty"** → run the bootstrap script.
- **Slow first encode** → expected on CPU; the weights download once and the
  model is cached afterward.

"""Axiom P1 search page.

Free-text query -> SPECTER2 encode -> Qdrant top-k semantic search, with a
venue/year filter bar applied as native Qdrant payload filters. Functionality
only; no styling polish (per P1 scope).

Run from the repo root:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from axiom import config, db
from axiom.embed import Specter2Encoder
from axiom.qdrant_client import AxiomQdrant

st.set_page_config(page_title="Axiom — Thesis Discovery", layout="wide")
st.title("Axiom — Semantic Paper Search (P1)")
st.caption(
    f"Collection `{config.COLLECTION_NAME}` · model `{config.MODEL_ID}` · "
    "synthetic corpus"
)


# --- Cached singletons -------------------------------------------------------
@st.cache_resource(show_spinner="Loading SPECTER2 encoder…")
def get_encoder() -> Specter2Encoder:
    return Specter2Encoder()


@st.cache_resource(show_spinner=False)
def get_store() -> AxiomQdrant:
    return AxiomQdrant()


@st.cache_data(show_spinner=False)
def get_filter_options() -> tuple[list[str], tuple[int, int] | None]:
    """Venue list + year bounds from SQLite (drives the filter bar)."""
    try:
        conn = db.connect()
        venues = db.distinct_venues(conn)
        bounds = db.year_bounds(conn)
        conn.close()
        return venues, bounds
    except Exception:
        return [], None


# --- Guard rails: Qdrant reachable & index non-empty -------------------------
store = get_store()
try:
    point_count = store.count()
except Exception:
    st.error(
        "⚠️ Cannot reach Qdrant. Start it with `docker compose up -d`, then "
        "run `python scripts/bootstrap_synthetic.py` to load the corpus."
    )
    st.stop()

if point_count == 0:
    st.warning(
        "The index is empty. Run `python scripts/bootstrap_synthetic.py` to "
        "load the 30-paper synthetic corpus, then refresh this page."
    )
    st.stop()


# --- Filter bar --------------------------------------------------------------
venues, bounds = get_filter_options()
with st.container():
    fcol1, fcol2, fcol3 = st.columns([2, 2, 1])
    with fcol1:
        # Empty selection = all venues (no silent filtering).
        selected_venues = st.multiselect(
            "Venue", options=venues, default=[],
            help="Leave empty to search all venues.",
        )
    with fcol2:
        if bounds:
            lo, hi = bounds
            years = list(range(lo, hi + 1))
            # Two selectboxes instead of a range slider: a range slider overlaps
            # its two value labels when both handles sit on the same year. From/To
            # makes a single-year pick explicit (From == To) with no overlap.
            ycol1, ycol2 = st.columns(2)
            with ycol1:
                y_from = st.selectbox("From year", years, index=0)
            with ycol2:
                y_to = st.selectbox("To year", years, index=len(years) - 1)
            # Tolerate From > To by normalizing the bounds.
            year_range = (min(y_from, y_to), max(y_from, y_to))
        else:
            year_range = None
    with fcol3:
        # Default to DEFAULT_TOP_K; cap at corpus size (no magic 30).
        top_k = st.number_input(
            "Top-K", min_value=1, max_value=point_count,
            value=min(config.DEFAULT_TOP_K, point_count), step=1,
        )


# --- Query -------------------------------------------------------------------
query = st.text_input(
    "Search query",
    placeholder="e.g. reducing hallucination in retrieval-augmented generation",
)

if query:
    encoder = get_encoder()
    qvec = encoder.encode_query(query)

    common = dict(
        top_k=int(top_k),
        venues=selected_venues or None,
        year_range=tuple(year_range) if year_range else None,
    )
    # Prefer hybrid (dense + sparse) when the index supports it; fall back to
    # pure dense otherwise (e.g. an index built before the hybrid upgrade).
    if store.supports_hybrid():
        hits = store.search_hybrid(query_vector=qvec, query_text=query, **common)
    else:
        hits = store.search(query_vector=qvec, **common)

    if not hits:
        st.info("No papers match the current filters. Loosen the venue/year filters.")
    else:
        df = pd.DataFrame(
            [
                {
                    "Score": round(h.score, 3),
                    "Title": h.title,
                    "Year": h.year,
                    "Venue": h.venue,
                    "Citations": h.cited_by_count,
                    "Concepts": ", ".join(h.concepts),
                }
                for h in hits
            ]
        )
        st.write(f"**{len(hits)} results**")
        st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Enter a query above to search the corpus.")

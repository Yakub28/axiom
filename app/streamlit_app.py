"""Axiom P1 search page.

Free-text query -> SPECTER2 encode -> Qdrant search (hybrid dense+sparse by
default, or dense-only via the toggle), with a venue/year filter bar. Results
render as expandable cards (title/DOI, concepts, abstract) and each card can
pivot to "similar papers". Functionality only; no styling polish.

Run from the repo root:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the repo root importable when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import streamlit.components.v1 as components

from axiom import config, db, gaps, graph
from axiom.embed import Specter2Encoder
from axiom.qdrant_client import AxiomQdrant, SearchHit

st.set_page_config(page_title="Axiom — Thesis Discovery", layout="wide")
st.title("Axiom — Semantic Search + Citation Graph")
st.caption(
    f"Collection `{config.COLLECTION_NAME}` · model `{config.MODEL_ID}` · "
    "OpenAlex corpus"
)


# --- Cached singletons -------------------------------------------------------
@st.cache_resource(show_spinner="Loading SPECTER2 encoder…")
def get_encoder() -> Specter2Encoder:
    return Specter2Encoder()


@st.cache_resource(show_spinner=False)
def get_store() -> AxiomQdrant:
    return AxiomQdrant()


@st.cache_resource(show_spinner="Loading citation graph…")
def get_graph():
    """In-memory citation graph from SQLite (decision OD6, NetworkX-first)."""
    return graph.load_graph()


@st.cache_data(show_spinner=False)
def get_influence_ranking(top_k: int = 50):
    """PageRank-ranked influential papers (cached; slice for the UI)."""
    return graph.influence(get_graph(), top_k=top_k)


@st.cache_data(show_spinner="Detecting communities & research gaps…")
def get_gap_analysis():
    """Communities + candidate research gaps (cached). Needs Qdrant vectors."""
    conn = db.connect()
    try:
        return gaps.analyze(get_graph(), conn, get_store().fetch_dense_vectors())
    finally:
        conn.close()


# Distinct, dark-background-friendly palette for community coloring.
_COMMUNITY_PALETTE = [
    "#4dabf7", "#ff922b", "#51cf66", "#cc5de8", "#ffd43b", "#ff6b6b",
    "#22b8cf", "#a9e34b", "#f783ac", "#748ffc", "#ffa94d", "#63e6be",
    "#e599f7", "#94d82d", "#ff8787", "#3bc9db",
]


def _community_color(cid: int) -> str:
    return _COMMUNITY_PALETTE[cid % len(_COMMUNITY_PALETTE)]


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


@st.cache_data(show_spinner=False)
def get_meta() -> dict[str, dict]:
    """Per-paper abstract/DOI/title from SQLite, keyed by paper_id.

    Qdrant payloads are intentionally lean; the cards enrich hits from SQLite,
    the durable source of truth.
    """
    try:
        conn = db.connect()
        ids = [r["openalex_id"] for r in db.iter_papers(conn)]
        rows = db.papers_by_ids(conn, ids)
        conn.close()
        return {
            pid: {"title": r["title"], "abstract": r["abstract"], "doi": r["doi"]}
            for pid, r in rows.items()
        }
    except Exception:
        return {}


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

meta = get_meta()
st.session_state.setdefault("similar_to", None)


# --- Result rendering --------------------------------------------------------
def render_hits(hits: list[SearchHit]) -> None:
    """Render hits as expandable cards with concepts, abstract, and a pivot."""
    if not hits:
        st.info("No papers match the current filters. Loosen the venue/year filters.")
        return
    st.write(f"**{len(hits)} results**")
    for h in hits:
        m = meta.get(h.paper_id, {})
        label = f"{h.score:.3f} · {h.title}  ({h.year} · {h.venue} · {h.cited_by_count} cites)"
        with st.expander(label):
            if m.get("doi"):
                st.markdown(f"[Open paper (DOI)](https://doi.org/{m['doi']})")
            if h.concepts:
                st.markdown(" ".join(f"`{c}`" for c in h.concepts))
            st.write(m.get("abstract") or "_No abstract available._")
            # Pivot: explore semantic neighbors of this paper.
            if st.button("🔎 Similar papers", key=f"sim_{h.paper_id}"):
                st.session_state["similar_to"] = h.paper_id
                st.rerun()


# --- Search tab --------------------------------------------------------------
def render_search() -> None:
    """Semantic/hybrid search with the venue/year filter bar."""
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
                # Two selectboxes instead of a range slider: a range slider
                # overlaps its two value labels when both handles sit on the same
                # year. From/To makes a single-year pick explicit (From == To).
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
            # Default to DEFAULT_TOP_K; cap at corpus size (no magic number).
            top_k = st.number_input(
                "Top-K", min_value=1, max_value=point_count,
                value=min(config.DEFAULT_TOP_K, point_count), step=1,
            )

    # Hybrid is only offered if the index has sparse vectors.
    if store.supports_hybrid():
        mode = st.radio(
            "Retrieval", ["Hybrid (dense + sparse)", "Dense only"],
            index=0, horizontal=True,
            help="Hybrid adds keyword/acronym matching (e.g. 'LoRA') on top of dense.",
        )
        use_hybrid = mode.startswith("Hybrid")
    else:
        use_hybrid = False
        st.caption("Retrieval: dense only (index has no sparse vectors — re-run the bootstrap for hybrid).")

    common = dict(
        top_k=int(top_k),
        venues=selected_venues or None,
        year_range=tuple(year_range) if year_range else None,
    )

    # Similar-papers pivot vs normal query view.
    similar_to = st.session_state.get("similar_to")
    if similar_to:
        title = meta.get(similar_to, {}).get("title", similar_to)
        st.subheader(f"Papers similar to: {title}")
        if st.button("← Back to search"):
            st.session_state["similar_to"] = None
            st.rerun()
        render_hits(store.similar_papers(similar_to, **common))
    else:
        query = st.text_input(
            "Search query",
            placeholder="e.g. reducing hallucination in retrieval-augmented generation",
        )
        if query:
            qvec = get_encoder().encode_query(query)
            if use_hybrid:
                hits = store.search_hybrid(query_vector=qvec, query_text=query, **common)
            else:
                hits = store.search(query_vector=qvec, **common)
            render_hits(hits)
        else:
            st.info("Enter a query above to search the corpus.")


# --- Citation-graph tab ------------------------------------------------------
_GRAPH3D_TEMPLATE = """
<div id="graph3d" style="width:100%;height:HEIGHTpx;background:#0b0f19;border-radius:10px;"></div>
<script src="https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"></script>
<script>
(function () {
  var el = document.getElementById('graph3d');
  function fail(msg) {
    el.innerHTML = '<p style="color:#ff8787;font-family:sans-serif;padding:1rem">' + msg + '</p>';
  }
  if (typeof ForceGraph3D === 'undefined') {
    fail('3D graph library could not load — check the browser has internet access.');
    return;
  }
  try {
    var data = __DATA__;
    el.style.position = 'relative';
    var Graph = ForceGraph3D()(el)
      .width(el.clientWidth || 800)
      .height(HEIGHT)
      .showNavInfo(false)
      .backgroundColor('#0b0f19')
      .graphData(data)
      .nodeLabel('name')
      .nodeVal('val')
      .nodeColor('color')
      .nodeOpacity(0.95)
      .nodeResolution(16)
      .linkColor(function () { return 'rgba(205,222,248,0.85)'; })
      .linkWidth(1.2)
      .linkDirectionalArrowLength(3.6)
      .linkDirectionalArrowRelPos(1)
      .linkDirectionalArrowColor(function () { return 'rgba(220,230,250,0.8)'; })
      .linkDirectionalParticles(3)
      .linkDirectionalParticleWidth(2)
      .linkDirectionalParticleColor(function () { return '#ffd43b'; })
      .linkDirectionalParticleSpeed(0.006)
      .onNodeClick(function (node) {
        var dist = 70;
        var ratio = 1 + dist / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
        Graph.cameraPosition(
          {x: (node.x || 0) * ratio, y: (node.y || 0) * ratio, z: (node.z || 0) * ratio},
          node, 800);
      });

    // Explicit starting camera so the scene is never a blank black frame.
    Graph.cameraPosition({ z: 320 });

    // Disable the (TrackballControls) wheel-zoom so the wheel scrolls the PAGE
    // instead of the canvas; zoom is via the on-screen buttons. (Guarded.)
    try {
      var ctrls = Graph.controls();
      if (ctrls) { ctrls.noZoom = true; ctrls.enableZoom = false; }
    } catch (e) {}
    // Cap long-range repulsion so disconnected clusters don't drift far apart.
    try { if (Graph.d3Force('charge')) Graph.d3Force('charge').strength(-45).distanceMax(220); } catch (e) {}
    // Auto-fit once the layout settles (guarded; runs after physics).
    setTimeout(function () { try { Graph.zoomToFit(600, 30); } catch (e) {} }, 1800);

    function dolly(f) {
      var c = Graph.cameraPosition();
      Graph.cameraPosition({x: c.x * f, y: c.y * f, z: c.z * f}, undefined, 250);
    }
    function mkBtn(txt, fn) {
      var b = document.createElement('button');
      b.textContent = txt;
      b.style.cssText = 'width:32px;height:32px;border:1px solid #93a4bd;border-radius:6px;' +
        'background:#5b6b85;color:#ffffff;font-size:17px;font-weight:600;line-height:1;' +
        'cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.4);';
      b.onmouseenter = function () { b.style.background = '#74859f'; };
      b.onmouseleave = function () { b.style.background = '#5b6b85'; };
      b.onclick = fn;
      return b;
    }
    var bar = document.createElement('div');
    bar.style.cssText = 'position:absolute;top:10px;right:12px;display:flex;gap:6px;z-index:5;';
    bar.appendChild(mkBtn('+', function () { dolly(0.8); }));
    bar.appendChild(mkBtn('–', function () { dolly(1.25); }));
    bar.appendChild(mkBtn('▣', function () { try { Graph.zoomToFit(400, 30); } catch (e) {} }));
    el.appendChild(bar);

    window.addEventListener('resize', function () { Graph.width(el.clientWidth || 800); });
  } catch (err) {
    fail('3D graph error: ' + (err && err.message ? err.message : err));
  }
})();
</script>
"""


def _graph_html(sub, focus_id: str | None = None,
                node_colors: dict[str, str] | None = None, height: int = 650) -> str:
    """Render a citation subgraph as an interactive 3D force-directed graph.

    Node size scales with in-degree within the subgraph (local prominence).
    Colour: per-node `node_colors` (e.g. by community) if given, the focused
    paper always orange, else default blue. Edges flow citing -> cited with
    directional particles. Library loads from CDN (needs internet in browser).
    """
    indeg = dict(sub.in_degree())
    max_in = max(indeg.values(), default=0) or 1
    nodes = []
    for nid, d in sub.nodes(data=True):
        title = d.get("title") or nid
        if focus_id and nid == focus_id:
            color = "#ff922b"
        elif node_colors and nid in node_colors:
            color = node_colors[nid]
        else:
            color = "#4dabf7"
        nodes.append({
            "id": nid,
            "name": (f"{title} ({d.get('year', '?')}) — "
                     f"{d.get('cited_by_count', 0)} cites · "
                     f"{indeg.get(nid, 0)} citing within view"),
            "val": 2 + 9 * (indeg.get(nid, 0) / max_in),
            "color": color,
        })
    links = [{"source": u, "target": v} for u, v in sub.edges()]
    payload = json.dumps({"nodes": nodes, "links": links})
    return _GRAPH3D_TEMPLATE.replace("HEIGHT", str(height)).replace("__DATA__", payload)


def _short(comm, k: int = 2) -> str:
    """First k distinctive concepts of a community, for compact labels."""
    return " · ".join(comm.labels[:k]) if comm.labels else f"cluster {comm.cid}"


def _render_gap_detail(g, gap) -> None:
    """Explain a candidate gap and list the top papers on each side."""
    st.markdown(
        f"**Why this is a candidate gap:** these two sub-topics are close in "
        f"meaning (centroid cosine **{gap.semantic_similarity:.2f}**) but only "
        f"**{gap.inter_citations}** citation(s) connect **{gap.a.size}** and "
        f"**{gap.b.size}** papers — a bridge largely unbuilt."
    )
    cola, colb = st.columns(2)
    for col, comm in ((cola, gap.a), (colb, gap.b)):
        with col:
            st.markdown(f"**{comm.label}** · {comm.size} papers")
            tops = sorted(comm.members,
                          key=lambda p: g.nodes[p].get("cited_by_count", 0),
                          reverse=True)[:5]
            for p in tops:
                d = g.nodes[p]
                st.markdown(f"- {d.get('title')}  _({d.get('year')})_")


def render_graph_view() -> None:
    """Research gaps + citation structure (communities, gaps, influence)."""
    st.subheader("Research gaps & citation structure")
    st.caption(
        "Sub-topics (communities) are detected in the citation graph; a candidate "
        "**research gap** is a pair of communities close in meaning yet barely "
        "citing each other — related literatures that haven't connected."
    )

    g = get_graph()
    gs = graph.stats(g)
    if gs["edges_in_corpus"] == 0:
        st.info("No in-corpus citation edges yet — ingest a connected corpus first.")
        return

    analysis = get_gap_analysis()
    node_colors = {pid: _community_color(cid) for pid, cid in analysis.node2c.items()}

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Papers", gs["papers"])
    mcol2.metric("In-corpus citations", gs["edges_in_corpus"])
    mcol3.metric("Sub-topics", len(analysis.communities))
    mcol4.metric("Candidate gaps", len(analysis.gaps))

    st.markdown("##### Interactive 3D graph")

    with st.container(border=True):
        ccol1, ccol2, ccol3 = st.columns([1.4, 2, 1])
        with ccol1:
            view = st.radio(
                "View", ["Research gaps", "Top influential"],
                help="Research gaps (default) highlights related-but-disconnected "
                     "clusters — the openings. 'Top influential' is for orientation: "
                     "the field's central papers. Click any node to inspect it.",
            )
        focus_id = None
        sel_gap = None
        with ccol2:
            if view == "Research gaps":
                if analysis.gaps:
                    opts = {
                        f"{_short(gp.a)} ⟷ {_short(gp.b)}  "
                        f"(sim {gp.semantic_similarity:.2f} · {gp.inter_citations} cites)": i
                        for i, gp in enumerate(analysis.gaps)
                    }
                    sel = st.selectbox("Candidate gap", list(opts.keys()))
                    sel_gap = analysis.gaps[opts[sel]]
                    members = set(sel_gap.a.members) | set(sel_gap.b.members)
                    sub = g.subgraph(members).copy()
                else:
                    sub = g.subgraph([]).copy()
            else:  # Top influential (orientation)
                v_n = st.slider("Papers to draw", 10, 50, 25, step=5)
                sub = graph.top_influential_subgraph(g, n=v_n)
        with ccol3:
            # Escape hatch: the WebGL canvas captures the mouse wheel (to zoom),
            # which blocks page scrolling while hovering it. Toggle off to scroll.
            show_3d = st.toggle("Show 3D graph", value=True,
                                help="Turn off to scroll the page freely past this section.")

    # Legend split: "what you're looking at" (left) vs "how to use it" (right).
    legend_focus = (
        '<span style="display:inline-flex;align-items:center;gap:6px;">'
        '<span style="width:13px;height:13px;background:#ff922b;border-radius:50%;'
        'display:inline-block;"></span>centered paper</span>'
    ) if focus_id else ""
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;justify-content:space-between;'
        'align-items:center;gap:16px;font-size:0.86rem;color:#374151;margin:2px 0 8px;">'
        # left group — what you're looking at
        '<div style="display:flex;flex-wrap:wrap;gap:18px;align-items:center;">'
        f'<span><b>{sub.number_of_nodes()}</b> papers · '
        f'<b>{sub.number_of_edges()}</b> citations in view</span>'
        '<span>🎨 colour = sub-topic cluster</span>'
        '<span style="display:inline-flex;align-items:center;gap:8px;">'
        '<span style="width:7px;height:7px;background:#868e96;border-radius:50%;display:inline-block;"></span>fewer'
        '<span style="width:17px;height:17px;background:#868e96;border-radius:50%;display:inline-block;"></span>'
        'more citations</span>'
        f'{legend_focus}'
        '</div>'
        # right group — how to use it
        '<div style="color:#6b7280;white-space:nowrap;">'
        'drag rotate · +/–/▣ zoom · click node to fly · wheel scrolls page'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if show_3d:
        components.html(
            _graph_html(sub, focus_id=focus_id, node_colors=node_colors, height=520),
            height=540, scrolling=False)

    # Gap detail + ranked list (gaps view only).
    if view == "Research gaps" and sel_gap is not None:
        _render_gap_detail(g, sel_gap)
        with st.expander(f"All {len(analysis.gaps)} candidate gaps (ranked)"):
            for i, gp in enumerate(analysis.gaps, 1):
                st.markdown(
                    f"{i}. **{_short(gp.a)}** ⟷ **{_short(gp.b)}** — "
                    f"semantic sim `{gp.semantic_similarity:.2f}`, "
                    f"`{gp.inter_citations}` citations between them"
                )

    st.divider()
    st.markdown("##### Influence ranking")
    n = st.slider("How many to rank", min_value=5, max_value=50, value=20, step=5)
    ranking = get_influence_ranking(50)[:n]

    for i, r in enumerate(ranking, 1):
        label = (f"{i}. {r.title}  ·  PR={r.pagerank:.4f}  ·  "
                 f"{r.local_in_degree} local / {r.cited_by_count} global cites  ·  {r.year}")
        with st.expander(label):
            m = meta.get(r.paper_id, {})
            if m.get("doi"):
                st.markdown(f"[Open paper (DOI)](https://doi.org/{m['doi']})")
            nb = graph.neighbors(g, r.paper_id)
            ext = sum(1 for x in nb.references if not x["in_corpus"])
            st.markdown(
                f"**Cited by {len(nb.cited_by)} papers in the corpus** · "
                f"cites {len(nb.references)} works ({ext} outside the corpus)"
            )
            if nb.cited_by:
                st.markdown("**Top corpus papers citing this:**")
                for c in nb.cited_by[:8]:
                    st.markdown(f"- {c['title']}  _({c['year']} · {c['cited_by_count']} cites)_")


# --- Tab dispatch ------------------------------------------------------------
tab_search, tab_graph = st.tabs(["🔍 Search", "🕸️ Citation graph"])
with tab_search:
    render_search()
with tab_graph:
    render_graph_view()

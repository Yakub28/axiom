"""Search-quality eval harness for Axiom P1.

Runs a fixed query set and prints the top-5 (score, title, year, venue) per
query, for one or more retrieval MODES so improvements are demonstrable rather
than eyeballed.

Modes:
    raw        Dense search with the query embedded as a *document* (the
               pre-upgrade behavior — terse queries land in a mushy region).
    expansion  Dense search with encode_query()'s abstract-shaped wrapping
               (Step 2). For "adapter" query paths this is the adapter vector.
    hybrid     Dense + sparse (BM25-style) fused with RRF (Step 3). Falls back
               with a clear message if the hybrid index isn't built yet.

Usage (from repo root):
    python scripts/eval_search.py                       # raw vs expansion vs hybrid
    python scripts/eval_search.py --modes raw expansion
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from axiom import config
from axiom.embed import Specter2Encoder
from axiom.qdrant_client import AxiomQdrant

# 5 full-phrased demo queries + 5 terse/awkward ones that currently fail.
QUERIES = [
    "reducing hallucination in retrieval-augmented generation",
    "parameter efficient fine-tuning with low-rank adapters",
    "low-resource machine translation with limited parallel data",
    "evaluating language models beyond accuracy",
    "chain-of-thought reasoning and self-consistency",
    "TOOLS for AI",
    "LoRA",
    "RAG",
    "how to make models hallucinate less",
    "cheap finetuning",
]

ALL_MODES = ["raw", "expansion", "hybrid"]


def run_mode(mode: str, query: str, encoder: Specter2Encoder,
             store: AxiomQdrant, top_k: int = 5):
    if mode == "raw":
        # Embed the query as if it were a document (no expansion template).
        vec = encoder.encode([query], abstracts=None)[0]
        return store.search(vec, top_k=top_k)
    if mode == "expansion":
        vec = encoder.encode_query(query)
        return store.search(vec, top_k=top_k)
    if mode == "hybrid":
        vec = encoder.encode_query(query)
        return store.search_hybrid(query_vector=vec, query_text=query, top_k=top_k)
    raise ValueError(f"unknown mode: {mode}")


def fmt_hits(hits) -> str:
    if not hits:
        return "      (no hits)"
    lines = []
    for h in hits:
        lines.append(f"      {h.score:6.3f}  [{h.year} {h.venue:<7}] {h.title}")
    spread = max(h.score for h in hits) - min(h.score for h in hits)
    lines.append(f"      score spread (top-{len(hits)}): {spread:.3f}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=ALL_MODES,
                    choices=ALL_MODES, help="which retrieval modes to compare")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    encoder = Specter2Encoder()
    store = AxiomQdrant()

    # Drop hybrid gracefully if the index has no sparse vectors yet.
    modes = list(args.modes)
    if "hybrid" in modes and not store.supports_hybrid():
        print("[eval] hybrid index not built (no sparse vectors) — skipping "
              "'hybrid'. Re-run scripts/bootstrap_synthetic.py after Step 3.\n")
        modes = [m for m in modes if m != "hybrid"]

    print(f"[eval] collection={config.COLLECTION_NAME} points={store.count()} "
          f"query_path={encoder.query_path} modes={modes}\n")

    for q in QUERIES:
        print(f"Q: {q!r}")
        for mode in modes:
            print(f"   [{mode}]")
            print(fmt_hits(run_mode(mode, q, encoder, store, args.top_k)))
        print()


if __name__ == "__main__":
    main()

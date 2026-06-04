"""Central configuration for Axiom P1.

Single source of truth for paths, Qdrant connection, collection name, and the
embedding model id. Every other module imports from here so there are no magic
strings scattered across the codebase.
"""
from __future__ import annotations

from pathlib import Path

# --- Paths -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "axiom.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"

# --- Qdrant ------------------------------------------------------------------
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
# Versioned collection name: bump the suffix when the embedding model or vector
# dimensionality changes so old/new points never mix.
COLLECTION_NAME = "axiom_v1"

# --- Embeddings --------------------------------------------------------------
# Committed team decision: SPECTER2, 768-dim. Do NOT silently swap models.
MODEL_ID = "allenai/specter2_base"
VECTOR_SIZE = 768

# Default search fan-out.
DEFAULT_TOP_K = 10

# --- Query-side embedding ----------------------------------------------------
# Terse queries ("LoRA", "TOOLS for AI") embed poorly when treated as documents
# and land in a mushy region of the space (flat ~0.82-0.88 scores). Two paths
# nudge the query vector toward the document region:
#   - "adapter":   SPECTER2 ad-hoc query adapter. Best, BUT the `adapters` lib
#                  pins transformers~=4.57, conflicting with our pinned 4.40.2,
#                  so it is unavailable without a committed-decision pin bump.
#   - "expansion": wrap the terse query in an abstract-shaped sentence. No new
#                  deps; works under the current pins. This is the active path.
QUERY_EXPANSION_TEMPLATE = "This paper presents {query} for natural language processing."

# --- Hybrid retrieval (dense + sparse) ---------------------------------------
# Dense SPECTER2 captures meaning; a sparse BM25-style vector captures exact
# terms/acronyms (LoRA, RAG, dataset names) that dense misses. Each point stores
# two named vectors; results are fused with Reciprocal Rank Fusion.
#
# NOTE: qdrant-client==1.9.0 has sparse vectors but NOT the Query-API fusion
# primitives (Prefetch/FusionQuery, client >= 1.10). We therefore run two native
# searches and fuse with RRF in Python — no pin bump required.
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
SPARSE_VOCAB_SIZE = 2 ** 20      # hashing-trick index space (fits uint32)
BM25_K1 = 1.5                    # BM25 term-frequency saturation
BM25_B = 0.75                    # BM25 length normalization
RRF_K = 60                       # reciprocal-rank-fusion constant
HYBRID_CANDIDATES = 20           # candidates pulled from each arm before fusion
# Tiny stopword set so terse keyword queries aren't dominated by glue words.
SPARSE_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "be", "by", "as", "at", "that", "this", "from", "how",
})

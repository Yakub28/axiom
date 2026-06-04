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

"""Qdrant wrapper for Axiom — the vector-store seam.

Owns collection lifecycle (versioned name `axiom_v1`), upserts, and
search-with-payload-filter. The UI talks to this module, never to raw Qdrant
objects, so the frontend stays decoupled from the vector store.

NOTE: this file is intentionally named `qdrant_client.py` to mirror the spec.
Python 3 uses absolute imports, so `from qdrant_client import QdrantClient`
below still resolves to the installed package, not this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    Range,
    VectorParams,
)

from axiom import config


@dataclass
class SearchHit:
    """One result row, rendered directly by the Streamlit page."""
    paper_id: str
    title: str
    year: int
    venue: str
    cited_by_count: int
    score: float
    concepts: list[str] = field(default_factory=list)


class AxiomQdrant:
    def __init__(self, host: str | None = None, port: int | None = None,
                 collection: str | None = None):
        self.collection = collection or config.COLLECTION_NAME
        self.client = QdrantClient(
            host=host or config.QDRANT_HOST,
            port=port or config.QDRANT_PORT,
        )

    # --- lifecycle ----------------------------------------------------------
    def recreate_collection(self) -> None:
        """Drop and recreate the collection. Used by the idempotent bootstrap."""
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(
                size=config.VECTOR_SIZE, distance=Distance.COSINE
            ),
        )

    def count(self) -> int:
        return self.client.count(self.collection, exact=True).count

    # --- writes -------------------------------------------------------------
    def upsert_papers(self, points: list[dict], vectors: list[list[float]]) -> None:
        """Upsert one point per paper.

        points: list of payload dicts with keys
            paper_id, title, year, venue, cited_by_count, concepts
        vectors: parallel list of 768-dim embeddings.
        """
        structs = []
        for idx, (payload, vec) in enumerate(zip(points, vectors)):
            structs.append(PointStruct(id=idx, vector=vec, payload=payload))
        self.client.upsert(collection_name=self.collection, points=structs)

    # --- reads --------------------------------------------------------------
    def search(
        self,
        query_vector: list[float],
        top_k: int = config.DEFAULT_TOP_K,
        venues: list[str] | None = None,
        year_range: tuple[int, int] | None = None,
    ) -> list[SearchHit]:
        """Dense search + native payload filter.

        Facets combine as AND; venues match as OR within the facet. Filters are
        applied by Qdrant (not post-filtered) so top_k is honored after filtering.
        """
        conditions = []
        if venues:
            conditions.append(
                FieldCondition(key="venue", match=MatchAny(any=list(venues)))
            )
        if year_range:
            lo, hi = year_range
            conditions.append(
                FieldCondition(key="year", range=Range(gte=lo, lte=hi))
            )
        query_filter = Filter(must=conditions) if conditions else None

        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        hits: list[SearchHit] = []
        for r in results:
            p = r.payload or {}
            hits.append(
                SearchHit(
                    paper_id=p.get("paper_id", ""),
                    title=p.get("title", ""),
                    year=p.get("year", 0),
                    venue=p.get("venue", ""),
                    cited_by_count=p.get("cited_by_count", 0),
                    concepts=p.get("concepts", []) or [],
                    score=r.score,
                )
            )
        return hits


# TODO(P2): the velocity engine and citation-graph tracks will read the same
# payload fields here (year, concepts, cited_by_count) to rank trending work and
# detected gaps — extend `search` with their filters rather than forking it.

"""Research-gap detection: where citation structure and meaning disagree.

The citation graph tells us a field's STRUCTURE (who builds on whom); the SPECTER2
embeddings tell us TOPICAL similarity (what's about the same thing). A research
gap is where the two disagree — two clusters of papers that are **semantically
close** (related problems) yet **barely cite each other** (the literatures never
connected). Those weak bridges between related sub-communities are candidate
openings for a thesis.

Pipeline:
  1. community detection (Louvain) on the undirected corpus citation graph
  2. label each community by its most *distinctive* OpenAlex concepts (TF-IDF
     across communities, so generic terms like "Computer science" don't win)
  3. an embedding centroid per community (mean of stored dense vectors)
  4. score community PAIRS: high centroid similarity + low inter-citation = gap

Pure-Python: networkx + numpy only (no torch, no scipy).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from axiom import graph as graphmod


@dataclass
class Community:
    cid: int
    members: list[str]
    labels: list[str]            # most distinctive concepts (topic label)
    size: int

    @property
    def label(self) -> str:
        return " · ".join(self.labels) if self.labels else f"cluster {self.cid}"


@dataclass
class GapCandidate:
    a: Community
    b: Community
    semantic_similarity: float   # cosine of centroids, ~[0,1]
    inter_citations: int         # citation edges between the two clusters
    gap_score: float             # higher = more related yet more disconnected


@dataclass
class GapAnalysis:
    node2c: dict[str, int]                 # paper_id -> community id (for coloring)
    communities: dict[int, Community]
    gaps: list[GapCandidate]


# ---------------------------------------------------------------------------
def detect_communities(g: nx.DiGraph, resolution: float = 1.0,
                       seed: int = 42) -> dict[str, int]:
    """Louvain communities on the undirected corpus citation graph.

    Returns {paper_id: community_id}, ids assigned largest-community-first.
    """
    sub = graphmod.corpus_subgraph(g).to_undirected()
    if sub.number_of_nodes() == 0:
        return {}
    comms = nx.community.louvain_communities(sub, seed=seed, resolution=resolution)
    node2c: dict[str, int] = {}
    for cid, members in enumerate(sorted(comms, key=len, reverse=True)):
        for n in members:
            node2c[n] = cid
    return node2c


def community_labels(conn, node2c: dict[str, int], top: int = 4) -> dict[int, list[str]]:
    """Most distinctive concepts per community via TF-IDF across communities.

    A concept that appears in every cluster (e.g. "Artificial intelligence")
    carries little signal; one concentrated in one cluster labels it well.
    """
    rows = conn.execute("SELECT paper_id, concept FROM concepts").fetchall()
    tf: dict[int, Counter] = defaultdict(Counter)
    for r in rows:
        cid = node2c.get(r["paper_id"])
        if cid is not None:
            tf[cid][r["concept"]] += 1
    n_comm = len(tf) or 1
    # document frequency = number of communities containing each concept
    df: Counter = Counter()
    for cid, cnt in tf.items():
        for concept in cnt:
            df[concept] += 1
    # Concepts present in most communities (e.g. "Computer science",
    # "Artificial intelligence") carry no distinguishing signal — drop them.
    generic = {c for c, d in df.items() if d >= max(2, 0.6 * n_comm)}
    labels: dict[int, list[str]] = {}
    for cid, cnt in tf.items():
        scored = {
            c: count * math.log(1 + n_comm / df[c])
            for c, count in cnt.items() if c not in generic
        }
        if not scored:                       # fallback if everything was generic
            scored = {c: count for c, count in cnt.items()}
        labels[cid] = [c for c, _ in sorted(scored.items(),
                                            key=lambda kv: kv[1], reverse=True)[:top]]
    return labels


def community_centroids(node2c: dict[str, int],
                        vectors: dict[str, list[float]]) -> dict[int, np.ndarray]:
    """Mean dense embedding per community (its position in semantic space)."""
    acc: dict[int, list[list[float]]] = defaultdict(list)
    for paper_id, cid in node2c.items():
        v = vectors.get(paper_id)
        if v is not None:
            acc[cid].append(v)
    return {cid: np.asarray(vs, dtype=float).mean(axis=0)
            for cid, vs in acc.items() if vs}


def inter_community_citations(g: nx.DiGraph,
                              node2c: dict[str, int]) -> Counter:
    """Count citation edges running between (not within) communities."""
    counts: Counter = Counter()
    for u, v in g.edges():
        cu, cv = node2c.get(u), node2c.get(v)
        if cu is not None and cv is not None and cu != cv:
            counts[frozenset((cu, cv))] += 1
    return counts


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def analyze(g: nx.DiGraph, conn, vectors: dict[str, list[float]], *,
            min_community_size: int = 4, top_k: int = 15,
            resolution: float = 1.0) -> GapAnalysis:
    """Full gap analysis: communities, labels, and ranked gap candidates.

    A gap candidate is a pair of sizable communities that are semantically close
    (similar centroids) but weakly connected by citations. `gap_score =
    similarity / (1 + inter_citations)` — related yet disconnected ranks highest.
    """
    node2c = detect_communities(g, resolution=resolution)
    if not node2c:
        return GapAnalysis({}, {}, [])

    labels = community_labels(conn, node2c)
    centroids = community_centroids(node2c, vectors)
    members: dict[int, list[str]] = defaultdict(list)
    for paper_id, cid in node2c.items():
        members[cid].append(paper_id)

    communities = {
        cid: Community(cid, members[cid], labels.get(cid, []), len(members[cid]))
        for cid in members
    }
    inter = inter_community_citations(g, node2c)

    candidates = [c for c in communities
                  if communities[c].size >= min_community_size and c in centroids]
    gaps: list[GapCandidate] = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            sim = _cosine(centroids[a], centroids[b])
            cites = int(inter.get(frozenset((a, b)), 0))
            gaps.append(GapCandidate(
                a=communities[a], b=communities[b],
                semantic_similarity=sim, inter_citations=cites,
                gap_score=sim / (1.0 + cites),
            ))
    gaps.sort(key=lambda x: x.gap_score, reverse=True)
    return GapAnalysis(node2c=node2c, communities=communities, gaps=gaps[:top_k])

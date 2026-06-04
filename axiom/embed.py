"""SPECTER2 abstract encoder.

Committed team decision: allenai/specter2_base, 768-dim. If no GPU is available
we fall back to CPU and emit a clear warning — we never silently switch models.

Encoding recipe is the canonical SPECTER one: concatenate title and abstract
with the tokenizer's [SEP] token and take the [CLS] token of the last hidden
state as the document embedding.
"""
from __future__ import annotations

import warnings
from typing import Sequence

import torch
from transformers import AutoModel, AutoTokenizer

from axiom import config


def _pick_device() -> str:
    """CUDA > Apple MPS > CPU. Warn (don't switch models) when no GPU."""
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    warnings.warn(
        "No GPU detected — running SPECTER2 (allenai/specter2_base) on CPU. "
        "Encoding will be slower but the model is unchanged.",
        RuntimeWarning,
        stacklevel=2,
    )
    return "cpu"


class Specter2Encoder:
    """Lazy-loaded SPECTER2 encoder. Construct once, reuse for all encode calls."""

    def __init__(self, model_id: str = config.MODEL_ID, device: str | None = None):
        self.model_id = model_id
        self.device = device or _pick_device()
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModel.from_pretrained(model_id).to(self.device)
        self.model.eval()
        # TODO(P2): load the SPECTER2 proximity adapter for better neighbor
        # quality once the embedding track is ready (needs adapter-transformers).

    @torch.no_grad()
    def encode(
        self,
        titles: Sequence[str],
        abstracts: Sequence[str] | None = None,
        batch_size: int = 16,
        max_length: int = 512,
    ) -> list[list[float]]:
        """Encode papers into 768-dim vectors.

        titles/abstracts are parallel sequences. If abstracts is None, titles
        are treated as standalone text (used for query encoding).
        """
        if abstracts is None:
            texts = list(titles)
        else:
            sep = self.tokenizer.sep_token or "[SEP]"
            texts = [f"{t or ''}{sep}{a or ''}" for t, a in zip(titles, abstracts)]

        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            ).to(self.device)
            output = self.model(**inputs)
            # [CLS] token = first position of last hidden state.
            cls = output.last_hidden_state[:, 0, :]
            vectors.extend(cls.cpu().tolist())
        return vectors

    def encode_query(self, query: str) -> list[float]:
        """Encode a single free-text query into one 768-dim vector."""
        return self.encode([query], abstracts=None)[0]

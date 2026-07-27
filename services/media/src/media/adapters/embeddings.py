"""Sentence-embedding adapter (all-MiniLM-L6-v2, 384-dim, CPU).

The same model embeds segment text (worker, at index time) and the search query
(API, at query time) — decided app-side so OpenSearch heap stays for search.
sentence-transformers (and its torch dependency) is imported lazily and the model
is loaded once, on first use.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings


class MiniLMEmbedder:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or Settings()
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._s.embedding_model, device="cpu")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        # normalize_embeddings so cosine similarity == dot product in OpenSearch.
        vecs = model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        result: list[list[float]] = vecs.tolist()
        return result

    @property
    def dimensions(self) -> int:
        return self._s.embedding_dims

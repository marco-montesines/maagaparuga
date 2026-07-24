"""OpenSearch transcript index — knn_vector mapping + hybrid (BM25 + k-NN) search.

The worker writes segment documents (text + 384-dim MiniLM embedding); the search
API reads them. Documents use a stable ``asset_id:index`` id so re-processing an
asset is idempotent. opensearch-py is imported lazily.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..domain.models import TranscriptSegment
from ..ports import SearchHit


class OpenSearchIndex:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or Settings()
        self._index = self._s.opensearch_index
        self._client: Any | None = None

    def _c(self) -> Any:
        if self._client is None:
            from opensearchpy import OpenSearch

            auth = (
                (self._s.opensearch_user, self._s.opensearch_password)
                if self._s.opensearch_user
                else None
            )
            self._client = OpenSearch(hosts=[self._s.opensearch_url], http_auth=auth)
        return self._client

    def ensure_index(self) -> None:
        """Create the knn index if absent (idempotent)."""
        client = self._c()
        if client.indices.exists(index=self._index):
            return
        client.indices.create(
            index=self._index,
            body={
                "settings": {"index": {"knn": True}},
                "mappings": {
                    "properties": {
                        "asset_id": {"type": "keyword"},
                        "care_recipient_id": {"type": "integer"},
                        "index": {"type": "integer"},
                        "start_ms": {"type": "integer"},
                        "end_ms": {"type": "integer"},
                        "text": {"type": "text"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": self._s.embedding_dims,
                            "method": {
                                "name": "hnsw",
                                "engine": "lucene",
                                "space_type": "cosinesimil",
                            },
                        },
                    }
                },
            },
        )

    def index_segments(
        self, segments: list[TranscriptSegment], vectors: list[list[float]]
    ) -> None:
        if not segments:
            return
        self.ensure_index()
        from opensearchpy import helpers

        actions = [
            {
                "_index": self._index,
                "_id": seg.segment_id,
                "_source": {
                    "asset_id": seg.asset_id,
                    "care_recipient_id": seg.care_recipient_id,
                    "index": seg.index,
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                    "text": seg.text,
                    "embedding": vec,
                },
            }
            for seg, vec in zip(segments, vectors, strict=True)
        ]
        helpers.bulk(self._c(), actions, refresh=True)

    def search(
        self, query: str, vector: list[float], *, care_recipient_id: int | None, limit: int
    ) -> list[SearchHit]:
        client = self._c()
        if not client.indices.exists(index=self._index):
            return []
        should = [
            {"match": {"text": query}},
            {"knn": {"embedding": {"vector": vector, "k": limit}}},
        ]
        bool_query: dict[str, Any] = {"should": should, "minimum_should_match": 1}
        if care_recipient_id is not None:
            bool_query["filter"] = [{"term": {"care_recipient_id": care_recipient_id}}]

        resp = client.search(
            index=self._index, body={"size": limit, "query": {"bool": bool_query}}
        )
        hits: list[SearchHit] = []
        for h in resp["hits"]["hits"]:
            src = h["_source"]
            hits.append(
                SearchHit(
                    asset_id=src["asset_id"],
                    care_recipient_id=src["care_recipient_id"],
                    index=src["index"],
                    start_ms=src["start_ms"],
                    end_ms=src["end_ms"],
                    text=src["text"],
                    score=h["_score"],
                )
            )
        return hits

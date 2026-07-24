"""OpenSearch transcript index — knn_vector mapping + hybrid (BM25 + k-NN) search.

The worker writes segment documents (text + 384-dim MiniLM embedding); the search
API reads them. Documents use a stable ``asset_id:index`` id so re-processing an
asset is idempotent. opensearch-py is imported lazily.

Ranking uses OpenSearch's native **hybrid query + a search pipeline** that
**min-max normalizes** each sub-query's scores before combining them. Summing raw
BM25 (unbounded) and cosine k-NN ([0,1]) scores would let BM25 dominate and make
the embedding almost irrelevant; normalization puts them on one scale so lexical
and semantic matches genuinely compete. The recipient filter is applied *inside*
each sub-query (a k-NN pre-filter), so vector recall is not lost to a global
top-k that gets filtered away afterwards.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..domain.models import TranscriptSegment
from ..ports import SearchHit

PIPELINE_NAME = "media-hybrid-search"


class OpenSearchIndex:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or Settings()
        self._index = self._s.opensearch_index
        self._client: Any | None = None
        self._pipeline_ready = False

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

    def _ensure_pipeline(self) -> None:
        """Register the normalization search pipeline (idempotent)."""
        if self._pipeline_ready:
            return
        self._c().transport.perform_request(
            "PUT",
            f"/_search/pipeline/{PIPELINE_NAME}",
            body={
                "description": "min-max normalize + combine BM25 and k-NN scores",
                "phase_results_processors": [
                    {
                        "normalization-processor": {
                            "normalization": {"technique": "min_max"},
                            "combination": {"technique": "arithmetic_mean"},
                        }
                    }
                ],
            },
        )
        self._pipeline_ready = True

    def ensure_index(self) -> None:
        """Create the knn index + search pipeline if absent (idempotent)."""
        client = self._c()
        if not client.indices.exists(index=self._index):
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
        self._ensure_pipeline()

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
        self._ensure_pipeline()

        term = {"term": {"care_recipient_id": care_recipient_id}}
        # BM25 sub-query, recipient-scoped.
        bm25: dict[str, Any] = {"match": {"text": query}}
        if care_recipient_id is not None:
            bm25 = {"bool": {"must": [{"match": {"text": query}}], "filter": [term]}}
        # k-NN sub-query with the recipient filter applied at candidate generation.
        knn_body: dict[str, Any] = {"vector": vector, "k": limit}
        if care_recipient_id is not None:
            knn_body["filter"] = term
        knn = {"knn": {"embedding": knn_body}}

        resp = client.search(
            index=self._index,
            body={"size": limit, "query": {"hybrid": {"queries": [bm25, knn]}}},
            params={"search_pipeline": PIPELINE_NAME},
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

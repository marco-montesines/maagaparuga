"""Composition root — assemble the concrete adapters into a MediaService.

Heavy adapters (S3, OpenSearch, MiniLM) are constructed here but their libraries
import lazily on first use, so building the service is cheap.
"""

from __future__ import annotations

from .adapters.catalog_postgres import PgCatalog
from .adapters.embeddings import MiniLMEmbedder
from .adapters.opensearch_index import OpenSearchIndex
from .adapters.queue_nats import NatsJobQueue
from .adapters.s3 import S3ObjectStore
from .adapters.whisper import FasterWhisperTranscriber
from .config import Settings
from .pipeline import TranscriptionPipeline
from .service import MediaService


def build_service(settings: Settings | None = None) -> MediaService:
    s = settings or Settings()
    return MediaService(
        store=S3ObjectStore(s),
        catalog=PgCatalog(s),
        queue=NatsJobQueue(s),
        index=OpenSearchIndex(s),
        embedder=MiniLMEmbedder(s),
    )


def build_pipeline(settings: Settings | None = None) -> TranscriptionPipeline:
    s = settings or Settings()
    return TranscriptionPipeline(
        store=S3ObjectStore(s),
        catalog=PgCatalog(s),
        transcriber=FasterWhisperTranscriber(s),
        embedder=MiniLMEmbedder(s),
        index=OpenSearchIndex(s),
    )

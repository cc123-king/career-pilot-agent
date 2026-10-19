from threading import RLock

from career_pilot.multimodal.models import ExtractedDocument
from career_pilot.rag.models import KnowledgeChunk
from career_pilot.rag.multimodal import (
    chunk_extracted_document,
)


class InMemoryKnowledgeStore:
    """Thread-safe storage for uploaded knowledge chunks."""

    def __init__(self) -> None:
        self._chunks_by_source: dict[
            str,
            tuple[KnowledgeChunk, ...],
        ] = {}
        self._lock = RLock()

    def add_document(
        self,
        document: ExtractedDocument,
        *,
        max_characters: int = 500,
    ) -> list[KnowledgeChunk]:
        """Chunk and add one extracted document."""

        chunks = chunk_extracted_document(
            document,
            max_characters=max_characters,
        )
        source_key = document.filename.casefold()

        stored_chunks = tuple(
            chunk.model_copy(deep=True)
            for chunk in chunks
        )

        with self._lock:
            self._chunks_by_source[source_key] = (
                stored_chunks
            )

        return [
            chunk.model_copy(deep=True)
            for chunk in chunks
        ]

    def list_chunks(self) -> list[KnowledgeChunk]:
        """Return a stable snapshot of all uploaded chunks."""

        with self._lock:
            return [
                chunk.model_copy(deep=True)
                for source_key in sorted(
                    self._chunks_by_source
                )
                for chunk in self._chunks_by_source[
                    source_key
                ]
            ]

    @property
    def document_count(self) -> int:
        """Return the number of uploaded documents."""

        with self._lock:
            return len(self._chunks_by_source)

    @property
    def chunk_count(self) -> int:
        """Return the number of uploaded chunks."""

        with self._lock:
            return sum(
                len(chunks)
                for chunks in self._chunks_by_source.values()
            )

    def clear(self) -> None:
        """Remove all uploaded knowledge."""

        with self._lock:
            self._chunks_by_source.clear()
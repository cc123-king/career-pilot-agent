"""Expand ranked small chunks into bounded, traceable source windows."""

from collections.abc import Sequence
from hashlib import sha256
from typing import Protocol

from career_pilot.rag.models import KnowledgeChunk, SearchHit


class RankedRetriever(Protocol):
    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]: ...


class NeighborWindowRetriever:
    """Read adjacent original chunks without additional embeddings.

    Windows never cross document/source/page/extraction boundaries. Their IDs
    and constituent IDs are deterministic. Only source text and whitespace are
    joined; no inferred information is inserted.
    """

    def __init__(
        self,
        chunks: Sequence[KnowledgeChunk],
        retriever: RankedRetriever,
        *,
        radius: int = 1,
    ):
        if radius < 0 or radius > 2:
            raise ValueError("相邻分块半径必须在0到2之间")
        self._retriever, self._radius = retriever, radius
        self._groups: dict[tuple, dict[int, KnowledgeChunk]] = {}
        self._ids = {}
        for chunk in chunks:
            if chunk.chunk_id in self._ids:
                raise ValueError("分块标识重复")
            self._ids[chunk.chunk_id] = chunk
            group = self._groups.setdefault(self._key(chunk), {})
            if chunk.position in group:
                raise ValueError("同一来源的分块位置重复")
            group[chunk.position] = chunk

    @staticmethod
    def _key(chunk):
        return (
            chunk.document_id,
            chunk.source,
            chunk.page_number,
            chunk.extraction_method,
            chunk.source_type,
        )

    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]:
        if not 1 <= top_k <= 8:
            raise ValueError("窗口数量必须在1到8之间")
        ranked = self._retriever.search(query, top_k=top_k * 2)
        covered, windows = set(), []
        for hit in ranked:
            center = self._ids.get(hit.chunk.chunk_id)
            if center is None or center != hit.chunk:
                raise ValueError("检索分块不属于当前快照")
            if center.chunk_id in covered:
                continue
            group = self._groups[self._key(center)]
            positions = {center.position}
            for direction in [-1, 1]:
                for distance in range(1, self._radius + 1):
                    position = center.position + direction * distance
                    if position not in group:
                        break
                    center_apis = {
                        scope.api for scope in center.source_scopes if scope.api
                    }
                    neighbor_apis = {
                        scope.api
                        for scope in group[position].source_scopes
                        if scope.api
                    }
                    if (
                        center_apis
                        and neighbor_apis
                        and not center_apis & neighbor_apis
                    ):
                        break
                    positions.add(position)
            members = [group[p] for p in sorted(positions)]
            text = "\n\n".join(c.content for c in members)
            if len(text) > 10000:
                members, text = [center], center.content
            member_ids = [c.chunk_id for c in members]
            chunk = (
                center
                if len(members) == 1
                else center.model_copy(
                    update={
                        "chunk_id": "window-"
                        + sha256("\0".join(member_ids).encode()).hexdigest()[:20],
                        "position": members[0].position,
                        "content": text,
                        "constituent_chunk_ids": member_ids,
                        "source_scopes": list(
                            {
                                s.model_dump_json(): s
                                for c in members
                                for s in c.source_scopes
                            }.values()
                        ),
                    }
                )
            )
            covered.update(member_ids)
            windows.append(hit.model_copy(update={"chunk": chunk}))
            if len(windows) == top_k:
                break
        return windows

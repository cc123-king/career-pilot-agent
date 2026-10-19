from collections.abc import Sequence

from career_pilot.rag.models import (
    ContextSource,
    KnowledgeChunk,
    RetrievalContext,
    SearchHit,
)
from career_pilot.text_utils import normalize_text


def build_retrieval_context(
    query: str,
    hits: Sequence[SearchHit],
    *,
    max_characters: int = 8_000,
) -> RetrievalContext:
    """Build traceable context that can be sent to a language model."""
    normalized_query = normalize_text(query)

    if not normalized_query:
        raise ValueError("查询不能为空")

    if max_characters < 200:
        raise ValueError("上下文最大长度不能小于 200")

    sections: list[str] = []
    sources: list[ContextSource] = []
    prefix = "请只根据以下资料回答问题。如果资料不足，请明确说明不知道，不要编造。\n\n"
    current_length = len(prefix)
    seen: dict[str, KnowledgeChunk] = {}

    for hit in hits:
        chunk = hit.chunk
        previous = seen.get(chunk.chunk_id)
        if previous is not None:
            if previous != chunk:
                raise ValueError("重复分块标识对应不同内容")
            continue
        seen[chunk.chunk_id] = chunk
        citation_id = len(sources) + 1

        metadata_lines: list[str] = []

        if chunk.page_number is not None:
            metadata_lines.append(f"页码：{chunk.page_number}")

        if chunk.source_type is not None:
            metadata_lines.append(f"文件类型：{chunk.source_type}")

        if chunk.extraction_method is not None:
            method_label = {
                "native_text": "原生文本",
                "ocr": "OCR",
            }[chunk.extraction_method]

            metadata_lines.append(f"提取方式：{method_label}")

        section_lines = [
            f"[资料{citation_id}]",
            f"标题：{chunk.title}",
            f"来源：{chunk.source}",
            *metadata_lines,
            f"分块：{chunk.chunk_id}",
            f"检索排序分数（不是答案置信度）：{hit.score:.3f}",
            *(
                ["组成分块：" + ", ".join(chunk.constituent_chunk_ids)]
                if chunk.constituent_chunk_ids
                else []
            ),
            f"内容：{chunk.content}",
        ]
        section = "\n".join(section_lines)

        separator_length = 2 if sections else 0
        projected_length = current_length + separator_length + len(section)

        if projected_length > max_characters:
            continue

        sections.append(section)
        current_length = projected_length

        sources.append(
            ContextSource(
                citation_id=citation_id,
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                source=chunk.source,
                score=hit.score,
                constituent_chunk_ids=chunk.constituent_chunk_ids,
                page_number=chunk.page_number,
                extraction_method=chunk.extraction_method,
                source_type=chunk.source_type,
            )
        )

    if sections:
        content = prefix + "\n\n".join(sections)
    else:
        content = (
            "没有检索到能够回答该问题的资料。请明确说明当前知识库信息不足，不要编造。"
        )

    return RetrievalContext(
        query=normalized_query,
        content=content,
        sources=sources,
    )

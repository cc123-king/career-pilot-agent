"""Offline API retrieval diagnostic using a user-supplied existing vector cache.

This post-run diagnostic never calls an embedding or chat service. Its spans do
not replace the first frozen evaluation labels or scores.
"""

import argparse
import hashlib
import json
import math
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument(
        "--knowledge-dir", type=Path, default=ROOT / "evaluation/technical_corpus"
    )
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "evaluation/answer_frozen_v7_cases.json"
    )
    parser.add_argument(
        "--spans", type=Path, default=ROOT / "evaluation/api_scope_diagnostic_v9.json"
    )
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--vector-scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve() / "src"))
    from career_pilot.rag.benchmark import canonical_text
    from career_pilot.rag.documents import chunk_document, load_knowledge_documents
    from career_pilot.rag.factory import DEFAULT_RAG_CONFIG, create_grounded_rag_service
    from career_pilot.text_utils import normalize_text

    read = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
    scope = read(args.vector_scope)
    files = sorted(args.knowledge_dir.glob("*.md"))
    expected = {Path(item["path"]).name: item["sha256"] for item in scope["documents"]}
    actual = {path.name: digest(path) for path in files}
    if expected != actual:
        raise ValueError("Corpus differs from vector provenance scope")
    vectors = read(args.vectors)
    dimensions = set()
    for vector in vectors.values():
        if (
            not isinstance(vector, list)
            or not vector
            or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in vector
            )
        ):
            raise ValueError("Invalid vector cache")
        dimensions.add(len(vector))
    if len(dimensions) != 1:
        raise ValueError("Mixed vector dimensions")

    class CachedEmbedder:
        def embed_texts(self, texts):
            return [vectors[normalize_text(text)] for text in texts]

        def embed_query(self, text):
            return vectors[normalize_text(text)]

    def deny_network(*args, **kwargs):
        raise RuntimeError("Offline diagnostic prohibits network")

    socket.socket.connect = deny_network
    chunks = [
        chunk
        for document in load_knowledge_documents(args.knowledge_dir)
        for chunk in chunk_document(
            document, max_characters=DEFAULT_RAG_CONFIG["max_characters"]
        )
    ]
    if any(normalize_text(chunk.content) not in vectors for chunk in chunks):
        raise ValueError("Required corpus vectors absent; no network fallback")
    labels = read(args.spans)
    spans = {case["case_id"]: case["evidence"] for case in labels["cases"]}
    cases = [case for case in read(args.dataset) if case["answerable"]]
    if set(spans) != {case["case_id"] for case in cases}:
        raise ValueError("Diagnostic labels do not match positive cases")
    raw = {
        path.name: canonical_text(path.read_text(encoding="utf-8")) for path in files
    }
    for evidence in spans.values():
        if any(
            canonical_text(item["anchor"]) not in raw[item["source"]]
            for item in evidence
        ):
            raise ValueError("Diagnostic span not in source")
    service = create_grounded_rag_service(chunks, None, CachedEmbedder())
    results = []
    for case in cases:
        hits = service._retriever.search(case["question"], top_k=6)
        checks = [
            any(
                hit.chunk.source == item["source"]
                and canonical_text(item["anchor"]) in canonical_text(hit.chunk.content)
                for hit in hits
            )
            for item in spans[case["case_id"]]
        ]
        results.append(
            {
                "case_id": case["case_id"],
                "source_facts_recalled": all(checks),
                "required_span_checks": checks,
                "retrieved_chunk_ids": [hit.chunk.chunk_id for hit in hits],
            }
        )
    report = {
        "kind": "post_run_source_span_diagnostic",
        "positive_questions": len(results),
        "source_fact_recall_at_6": sum(row["source_facts_recalled"] for row in results),
        "paid_chat_calls": 0,
        "embedding_calls": 0,
        "not_answer_accuracy": True,
        "not_original_frozen_score": True,
        "configuration": DEFAULT_RAG_CONFIG,
        "embedding_provenance": scope["embedding"],
        "vector_cache_sha256": digest(args.vectors),
        "span_manifest_sha256": digest(args.spans),
        "documents_sha256": actual,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in ("results", "documents_sha256")
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

"""Retain source declarations/antecedents and prefer exact API identities."""

import re
from collections.abc import Sequence

from career_pilot.rag.models import KnowledgeChunk, SearchHit, SourceScope

DECLARATION = re.compile(
    r"^\.\.\s+(class|function|method|coroutinefunction|awaitablefunction)::\s*([A-Za-z_][A-Za-z0-9_.]*)"
)
MODULE = re.compile(r"^\.\.\s+(?:currentmodule|module)::\s*([A-Za-z_][A-Za-z0-9_.]*)")
QUERY_API = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+|[A-Za-z_][A-Za-z0-9_]*(?=\s*\()|[A-Za-z_][A-Za-z0-9_]*_[A-Za-z_][A-Za-z0-9_]*"
)
ASSIGNMENT = re.compile(
    r"([A-Za-z_][A-Za-z0-9_.]*)\s*(?:(?:被)?设(?:置)?为|(?:的)?值为|=|\bis\b)\s*[`*\"']*(True|False|None|true|false|null)(?![A-Za-z0-9_])"
)


class ScopeMismatchError(ValueError):
    """A generated assignment changes the identifier named by its source."""


class ScopeTracker:
    def __init__(self):
        self.module = self.owner = self.api = self.declaration = ""

    def observe(self, paragraph: str) -> None:
        module = MODULE.match(paragraph)
        if module:
            self.module, self.owner, self.api, self.declaration = module[1], "", "", ""
        declaration = DECLARATION.match(paragraph)
        if declaration:
            kind, name = declaration.groups()
            if kind == "class":
                self.owner = name
            elif kind != "method":
                self.owner = ""
            if kind == "method" and "." not in name and self.owner:
                name = self.owner + "." + name
            self.api = (
                self.module + "."
                if self.module and not name.startswith(self.module + ".")
                else ""
            ) + name
            self.declaration = paragraph[:800]
        elif paragraph.startswith("#"):
            self.owner = self.api = self.declaration = ""

    def context(self, paragraph: str, start: int, length: int) -> SourceScope:
        if len(paragraph) <= 1600:
            text = paragraph
        else:
            left = max(0, start - 300)
            text = paragraph[left : min(len(paragraph), left + min(1600, length + 600))]
        return SourceScope(api=self.api[:200], declaration=self.declaration, text=text)


def api_names(query: str) -> set[str]:
    return {name.casefold() for name in QUERY_API.findall(query)}


def match_api(query_names: set[str], candidate: str) -> int:
    name = candidate.casefold()
    return (
        max(
            (
                3
                if q == name
                else 2
                if name.endswith("." + q) or q.endswith("." + name)
                else 0
                for q in query_names
            ),
            default=0,
        )
        if name
        else 0
    )


class APIAwareRetriever:
    """Prefer matching declarations without discarding the normal hybrid fallback."""

    def __init__(self, chunks: Sequence[KnowledgeChunk], retriever):
        self._chunks, self._retriever = list(chunks), retriever

    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k 必须大于等于1")
        hits = self._retriever.search(query, top_k=top_k)
        names = api_names(query)
        if not names:
            return hits
        by_id = {h.chunk.chunk_id: h for h in hits}
        rank = {h.chunk.chunk_id: i for i, h in enumerate(hits)}
        anchors = []
        for chunk in self._chunks:
            degree = max(
                (match_api(names, scope.api) for scope in chunk.source_scopes),
                default=0,
            )
            if degree:
                hit = by_id.get(chunk.chunk_id) or SearchHit(
                    chunk=chunk, score=0.5, matched_terms=sorted(names)
                )
                anchors.append(
                    (degree, rank.get(chunk.chunk_id, len(hits)), chunk.position, hit)
                )
        anchors.sort(
            key=lambda item: (-item[0], item[1], item[2], item[3].chunk.chunk_id)
        )
        ordered = [item[3] for item in anchors]
        included = {h.chunk.chunk_id for h in ordered}
        ordered.extend(
            h
            for h in hits
            if h.chunk.chunk_id not in included
            and (not anchors or not any(scope.api for scope in h.chunk.source_scopes))
        )
        return ordered[:top_k]


def select_scopes(scopes: list[SourceScope], quotes: list[str]) -> list[SourceScope]:
    compact = lambda text: re.sub(r"\s+", "", text)
    selected, seen = [], set()
    for scope in scopes:
        text = compact(scope.text)
        if any(
            compact(q) in text or compact(q)[:24] in text or compact(q)[-24:] in text
            for q in quotes
        ):
            identity = (scope.api, scope.declaration, scope.text)
            if identity not in seen:
                seen.add(identity)
                selected.append(scope)
    return selected


def validate_assignment_scope(text: str, evidence: list, passages: dict) -> None:
    """Reject renamed Boolean/null assignment targets even if an audit agrees.

    This is a narrow deterministic check, not a general entailment proof.
    Context is derived from the source paragraph, never the user question.
    """
    targets = ASSIGNMENT.findall(text)
    if not targets:
        return
    support = []
    for quote in evidence:
        passage = passages.get(quote.citation_id)
        if passage is None:
            continue
        support.append(quote.quote)
        support.extend(
            scope.declaration + " " + scope.text
            for scope in select_scopes(passage.source_scopes, [quote.quote])
        )
    support = " ".join(support)
    for target, _ in targets:
        # Identifiers are case sensitive, and must occur as whole identifiers.
        if not re.search(
            r"(?<![A-Za-z0-9_.])" + re.escape(target) + r"(?![A-Za-z0-9_.])", support
        ):
            raise ScopeMismatchError("assignment_target_not_in_cited_source_scope")

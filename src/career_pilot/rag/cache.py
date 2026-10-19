"""A single-flight cache keyed by the complete knowledge/configuration snapshot."""

import hashlib
import json
from collections.abc import Callable, Sequence
from threading import RLock
from typing import TypeVar

from pydantic import BaseModel, SecretStr

from career_pilot.rag.models import KnowledgeChunk

T = TypeVar("T")


def _json_value(value):
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, BaseModel):
        return value.model_dump()
    raise TypeError("Unsupported snapshot value")


def snapshot_fingerprint(
    chunks: Sequence[KnowledgeChunk],
    configuration: dict,
    *settings: object,
) -> str:
    # Raw secrets and personal text are only hashed in memory, never stored/logged.
    payload = json.dumps(
        {
            "chunks": [c.model_dump() for c in chunks],
            "configuration": configuration,
            "settings": settings,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=_json_value,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SnapshotCache:
    """Serialize builds so concurrent first requests cannot duplicate index calls."""

    def __init__(self):
        self._lock = RLock()
        self._key = None
        self._value = None

    def get_or_create(self, key: str, factory: Callable[[], T]) -> T:
        with self._lock:
            if self._key != key:
                value = factory()  # Failure never commits a mismatched snapshot.
                self._key, self._value = key, value
            return self._value

    def clear(self):
        with self._lock:
            self._key = self._value = None

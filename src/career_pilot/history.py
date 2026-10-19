"""Durable local review history and uploaded knowledge snapshots."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from career_pilot.rag.knowledge_store import InMemoryKnowledgeStore
from career_pilot.rag.models import KnowledgeChunk
from career_pilot.rag.multimodal import chunk_extracted_document


def default_path():
    return Path(
        os.getenv(
            "CAREER_STATE_DB",
            str(Path(__file__).resolve().parents[2] / "data" / "career.sqlite3"),
        )
    )


class HistoryStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS knowledge(filename TEXT PRIMARY KEY, chunks TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, payload, review_id=None):
        review_id = review_id or uuid4().hex
        stamp = datetime.now(UTC).isoformat()
        payload = dict(payload, review_id=review_id)
        with self.connect() as db:
            old = db.execute(
                "SELECT created_at FROM reviews WHERE id=?", (review_id,)
            ).fetchone()
            db.execute(
                "INSERT OR REPLACE INTO reviews VALUES(?,?,?,?,?,?)",
                (
                    review_id,
                    payload["filename"],
                    payload["status"],
                    old["created_at"] if old else stamp,
                    stamp,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
        return payload

    def get(self, review_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM reviews WHERE id=?", (review_id,)
            ).fetchone()
            return json.loads(row["payload"]) if row else None

    def list(self, limit=30):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,title,status,created_at,updated_at FROM reviews ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
            ]

    def delete(self, review_id):
        with self.connect() as db:
            return (
                db.execute("DELETE FROM reviews WHERE id=?", (review_id,)).rowcount > 0
            )


class PersistentKnowledgeStore(InMemoryKnowledgeStore):
    def __init__(self, path=None):
        super().__init__()
        self.history = HistoryStore(path)

    def add_document(self, document, *, max_characters=500):
        chunks = chunk_extracted_document(document, max_characters=max_characters)
        with self.history.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO knowledge VALUES(?,?)",
                (
                    document.filename.casefold(),
                    json.dumps(
                        [c.model_dump(mode="json") for c in chunks], ensure_ascii=False
                    ),
                ),
            )
        return chunks

    def list_chunks(self):
        with self.history.connect() as db:
            return [
                KnowledgeChunk.model_validate(c)
                for row in db.execute("SELECT chunks FROM knowledge ORDER BY filename")
                for c in json.loads(row["chunks"])
            ]

    @property
    def document_count(self):
        with self.history.connect() as db:
            return db.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]

    @property
    def chunk_count(self):
        return len(self.list_chunks())

    def clear(self):
        with self.history.connect() as db:
            db.execute("DELETE FROM knowledge")

"""SQLite persistence for job application tracking and analysis snapshots."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import AnalysisResult, ApplicationCreate, ApplicationRecord, utc_now_iso


class ApplicationRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    match_score INTEGER NOT NULL DEFAULT 0,
                    resume_name TEXT NOT NULL DEFAULT '',
                    jd_excerpt TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    analysis_json TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_applications_status
                    ON applications(status);
                CREATE INDEX IF NOT EXISTS idx_applications_created_at
                    ON applications(created_at DESC);
                """
            )

    def create(
        self,
        data: ApplicationCreate,
        analysis: AnalysisResult | None = None,
    ) -> ApplicationRecord:
        now = utc_now_iso()
        analysis_json = analysis.model_dump_json() if analysis else ""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO applications (
                    company, role, status, match_score, resume_name, jd_excerpt,
                    notes, analysis_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.company,
                    data.role,
                    data.status,
                    data.match_score,
                    data.resume_name,
                    data.jd_excerpt,
                    data.notes,
                    analysis_json,
                    now,
                    now,
                ),
            )
            record_id = int(cursor.lastrowid)
        return self.get(record_id)

    def get(self, record_id: int) -> ApplicationRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"不存在投递记录：{record_id}")
        return self._to_model(row)

    def list(self, limit: int = 100) -> list[ApplicationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM applications ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def update_status(self, record_id: int, status: str, notes: str | None = None) -> ApplicationRecord:
        now = utc_now_iso()
        with self._connect() as connection:
            if notes is None:
                cursor = connection.execute(
                    "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                    (status, now, record_id),
                )
            else:
                cursor = connection.execute(
                    "UPDATE applications SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
                    (status, notes, now, record_id),
                )
        if cursor.rowcount == 0:
            raise KeyError(f"不存在投递记录：{record_id}")
        return self.get(record_id)

    def delete(self, record_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM applications WHERE id = ?", (record_id,))
        return cursor.rowcount > 0

    def get_analysis(self, record_id: int) -> AnalysisResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT analysis_json FROM applications WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"不存在投递记录：{record_id}")
        if not row["analysis_json"]:
            return None
        return AnalysisResult.model_validate(json.loads(row["analysis_json"]))

    @staticmethod
    def _to_model(row: sqlite3.Row) -> ApplicationRecord:
        return ApplicationRecord(
            id=row["id"],
            company=row["company"],
            role=row["role"],
            status=row["status"],
            match_score=row["match_score"],
            resume_name=row["resume_name"],
            jd_excerpt=row["jd_excerpt"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class Settings:
    """Runtime settings.

    Demo mode is intentionally the default so a new user can run the project
    without an API key and without accidentally creating API charges.
    """

    project_root: Path = PROJECT_ROOT
    llm_provider: str = "demo"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    compatible_api_key: str = ""
    compatible_base_url: str = ""
    compatible_model: str = ""
    database_path: Path = PROJECT_ROOT / "data" / "applications.db"
    app_host: str = "127.0.0.1"
    app_port: int = 7860
    api_port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        database_value = os.getenv("DATABASE_PATH", "data/applications.db")
        database_path = Path(database_value)
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path

        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "demo").strip().lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip(),
            compatible_api_key=os.getenv("LLM_API_KEY", "").strip(),
            compatible_base_url=os.getenv("LLM_BASE_URL", "").strip(),
            compatible_model=os.getenv("LLM_MODEL", "").strip(),
            database_path=database_path,
            app_host=os.getenv("APP_HOST", "127.0.0.1").strip(),
            app_port=int(os.getenv("APP_PORT", "7860")),
            api_port=int(os.getenv("API_PORT", "8000")),
        )

    @property
    def ai_enabled(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "compatible":
            return bool(
                self.compatible_api_key
                and self.compatible_base_url
                and self.compatible_model
            )
        return False

    @property
    def knowledge_path(self) -> Path:
        return self.project_root / "knowledge" / "agent_job_knowledge.md"


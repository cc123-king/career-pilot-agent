import math
import os
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import Field, SecretStr

from career_pilot.models import StrictModel
from career_pilot.text_utils import normalize_text


class EmbeddingSettings(StrictModel):
    """Configuration for the embedding model."""

    api_key: SecretStr
    base_url: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"^https?://",
    )
    model: str = Field(min_length=1, max_length=100)


def load_embedding_settings(
    env_file: str | Path | None = ".env",
) -> EmbeddingSettings:
    """Load embedding settings from environment variables."""

    if env_file is not None:
        load_dotenv(dotenv_path=env_file)

    environment_values = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY", "").strip(),
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL", "").strip(),
        "EMBEDDING_MODEL": os.getenv(
            "EMBEDDING_MODEL",
            "",
        ).strip(),
    }

    missing_names = [name for name, value in environment_values.items() if not value]

    if missing_names:
        missing_text = ", ".join(missing_names)
        raise ValueError(f"缺少向量模型配置：{missing_text}")

    return EmbeddingSettings(
        api_key=environment_values["LLM_API_KEY"],
        base_url=environment_values["LLM_BASE_URL"],
        model=environment_values["EMBEDDING_MODEL"],
    )


class EmbeddingClient:
    """Convert text into vectors through an embedding model."""

    def __init__(
        self,
        settings: EmbeddingSettings,
        client: OpenAI | None = None,
    ) -> None:
        self._settings = settings
        self.request_count = 0
        self._client = client or OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=30.0,
            max_retries=0,
        )

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """Convert multiple texts into vectors in one request."""

        normalized_texts = [normalize_text(text) for text in texts]

        if not normalized_texts:
            raise ValueError("待向量化文本列表不能为空")

        if any(not text for text in normalized_texts):
            raise ValueError("待向量化文本不能为空")

        vectors: list[list[float]] = []
        # text-embedding-v4 accepts at most 10 input texts per request.
        for start in range(0, len(normalized_texts), 10):
            batch = normalized_texts[start : start + 10]
            self.request_count += 1
            response = self._client.embeddings.create(
                model=self._settings.model,
                input=batch,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            if len(ordered) != len(batch):
                raise RuntimeError("向量模型返回数量不一致")
            if [item.index for item in ordered] != list(range(len(batch))):
                raise RuntimeError("向量模型返回索引不一致")
            vectors.extend(list(item.embedding) for item in ordered)

        if any(not vector for vector in vectors):
            raise RuntimeError("向量模型返回了空向量")

        dimension = len(vectors[0])

        if any(len(vector) != dimension for vector in vectors):
            raise RuntimeError("向量维度不一致")

        if any(
            not all(
                isinstance(v, (int, float))
                and not isinstance(v, bool)
                and math.isfinite(v)
                for v in vector
            )
            or not any(v != 0 for v in vector)
            for vector in vectors
        ):
            raise RuntimeError("向量包含非有限数值或零向量")
        return vectors

    def embed_query(self, query: str) -> list[float]:
        """Convert one search query into a vector."""

        return self.embed_texts([query])[0]

from types import SimpleNamespace

import pytest

from career_pilot.rag.embeddings import (
    EmbeddingClient,
    EmbeddingSettings,
)


class FakeEmbeddings:
    """Fake implementation of the embeddings API."""

    def __init__(
        self,
        data: list[SimpleNamespace],
    ) -> None:
        self._data = data
        self.last_request: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.last_request = kwargs
        return SimpleNamespace(data=self._data)


class FakeOpenAI:
    """Fake OpenAI-compatible SDK client."""

    def __init__(
        self,
        data: list[SimpleNamespace],
    ) -> None:
        self.embeddings = FakeEmbeddings(data)


def make_settings() -> EmbeddingSettings:
    return EmbeddingSettings(
        api_key="test-api-key",
        base_url=("https://dashscope.aliyuncs.com/compatible-mode/v1"),
        model="text-embedding-v4",
    )


def make_client(
    data: list[SimpleNamespace],
) -> tuple[EmbeddingClient, FakeOpenAI]:
    fake_client = FakeOpenAI(data)
    embedding_client = EmbeddingClient(
        make_settings(),
        client=fake_client,
    )

    return embedding_client, fake_client


def test_embed_texts_sends_batch_and_restores_order() -> None:
    embedding_client, fake_client = make_client(
        [
            SimpleNamespace(
                index=1,
                embedding=[0.0, 1.0],
            ),
            SimpleNamespace(
                index=0,
                embedding=[1.0, 0.0],
            ),
        ]
    )

    vectors = embedding_client.embed_texts(
        [
            "  Python   Agent  ",
            "RAG\n检索",
        ]
    )

    assert vectors == [
        [1.0, 0.0],
        [0.0, 1.0],
    ]
    assert fake_client.embeddings.last_request == {
        "model": "text-embedding-v4",
        "input": [
            "Python Agent",
            "RAG 检索",
        ],
    }


def test_embed_query_returns_one_vector() -> None:
    embedding_client, fake_client = make_client(
        [
            SimpleNamespace(
                index=0,
                embedding=[0.2, 0.8],
            )
        ]
    )

    vector = embedding_client.embed_query("Agent 项目怎么介绍？")

    assert vector == [0.2, 0.8]
    assert fake_client.embeddings.last_request == {
        "model": "text-embedding-v4",
        "input": ["Agent 项目怎么介绍？"],
    }


@pytest.mark.parametrize(
    "texts",
    [
        [],
        ["   "],
    ],
)
def test_embed_texts_rejects_empty_input(
    texts: list[str],
) -> None:
    embedding_client, fake_client = make_client([])

    with pytest.raises(ValueError, match="不能为空"):
        embedding_client.embed_texts(texts)

    assert fake_client.embeddings.last_request is None


def test_embed_texts_rejects_wrong_result_count() -> None:
    embedding_client, _ = make_client(
        [
            SimpleNamespace(
                index=0,
                embedding=[1.0, 0.0],
            )
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="返回数量不一致",
    ):
        embedding_client.embed_texts(["第一段", "第二段"])


def test_embed_texts_rejects_empty_vector() -> None:
    embedding_client, _ = make_client(
        [
            SimpleNamespace(
                index=0,
                embedding=[],
            )
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="返回了空向量",
    ):
        embedding_client.embed_texts(["测试文本"])


def test_embed_texts_rejects_inconsistent_dimensions() -> None:
    embedding_client, _ = make_client(
        [
            SimpleNamespace(
                index=0,
                embedding=[1.0, 0.0],
            ),
            SimpleNamespace(
                index=1,
                embedding=[0.0, 1.0, 0.5],
            ),
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="向量维度不一致",
    ):
        embedding_client.embed_texts(["第一段", "第二段"])


def test_large_embedding_input_is_split_into_provider_safe_batches():
    class BatchAPI:
        def __init__(self):
            self.calls = []

        def create(self, *, model, input):
            self.calls.append(list(input))
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=i, embedding=[float(text), 1.0])
                    for i, text in reversed(list(enumerate(input)))
                ]
            )

    api = BatchAPI()
    client = EmbeddingClient(make_settings(), client=SimpleNamespace(embeddings=api))
    vectors = client.embed_texts([str(i) for i in range(23)])
    assert [len(batch) for batch in api.calls] == [10, 10, 3]
    assert [v[0] for v in vectors] == list(range(23))
    assert client.request_count == 3


def test_duplicate_response_indexes_cannot_silently_misalign_texts():
    client, _ = make_client(
        [
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
            SimpleNamespace(index=0, embedding=[0.0, 1.0]),
        ]
    )
    with pytest.raises(RuntimeError, match="索引不一致"):
        client.embed_texts(["first", "second"])


@pytest.mark.parametrize(
    "vector",
    [
        [float("nan"), 1.0],
        [float("inf"), 1.0],
        [False, 1.0],
        [0.0, 0.0],
    ],
)
def test_embedding_rejects_non_finite_boolean_and_zero_vectors(vector):
    client, _ = make_client([SimpleNamespace(index=0, embedding=vector)])
    with pytest.raises(RuntimeError, match="非有限数值或零向量"):
        client.embed_texts(["有效文本"])


@pytest.mark.parametrize("vector", [[float("nan"), 1.0], [float("inf"), 1.0]])
def test_similarity_rejects_non_finite_values_before_ranking(vector):
    from career_pilot.rag.vector_index import cosine_similarity

    with pytest.raises(ValueError, match="有限数值"):
        cosine_similarity(vector, [1.0, 1.0])

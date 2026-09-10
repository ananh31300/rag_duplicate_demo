from __future__ import annotations

from typing import Any

from app.embedding import OpenRouterEmbedder, OpenRouterEmbeddingConfig
from app.normalization import content_hash, normalize_text


class FakeResponse:
    def __init__(self, embedding: list[float]) -> None:
        self._embedding = embedding

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"data": [{"embedding": self._embedding}]}


def test_unicode_nfc_and_whitespace_produce_same_identity() -> None:
    composed = "Ki-ốt  thông minh"
    decomposed = "Ki-o\u0302́t\n thông minh"

    assert normalize_text(composed) == normalize_text(decomposed)
    assert content_hash(normalize_text(composed)) == content_hash(
        normalize_text(decomposed)
    )


def test_content_hash_is_stable_for_reordered_object_keys() -> None:
    assert content_hash({"number": "309", "year": 2026}) == content_hash(
        {"year": 2026, "number": "309"}
    )


def test_openrouter_adapter_accepts_bge_m3_vector(monkeypatch: Any) -> None:
    embedder = OpenRouterEmbedder(
        OpenRouterEmbeddingConfig(
            model="BAAI/bge-m3",
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
        )
    )
    expected = [0.0] * 1024
    monkeypatch.setattr(
        embedder._session,
        "post",
        lambda *args, **kwargs: FakeResponse(expected),
    )

    assert embedder.embed("xác thực VNeID") == expected


def test_openrouter_adapter_rejects_wrong_vector_dimension(monkeypatch: Any) -> None:
    embedder = OpenRouterEmbedder(
        OpenRouterEmbeddingConfig(
            model="BAAI/bge-m3",
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
        )
    )
    monkeypatch.setattr(
        embedder._session,
        "post",
        lambda *args, **kwargs: FakeResponse([0.0] * 3),
    )

    try:
        embedder.embed("xác thực VNeID")
    except RuntimeError as error:
        assert "Expected 1024 dimensions" in str(error)
    else:
        raise AssertionError("A three-dimensional response must be rejected")


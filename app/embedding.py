from __future__ import annotations

from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass(frozen=True)
class OpenRouterEmbeddingConfig:
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 30.0


class OpenRouterEmbedder:
    dimensions = 1024

    def __init__(self, config: OpenRouterEmbeddingConfig) -> None:
        if not config.api_key:
            raise ValueError("EMBEDDING_API_KEY is required")
        self._config = config
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(("POST",)),
        )
        self._session = requests.Session()
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    @property
    def name(self) -> str:
        return self._config.model

    def embed(self, text: str) -> list[float]:
        response = self._session.post(
            f"{self._config.base_url.rstrip('/')}/embeddings",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self._config.model, "input": text},
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        embedding = payload["data"][0]["embedding"]
        if len(embedding) != self.dimensions:
            raise RuntimeError(
                f"Expected {self.dimensions} dimensions, received {len(embedding)}"
            )
        return [float(value) for value in embedding]


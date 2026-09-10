from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str
    rabbitmq_url: str
    opensearch_url: str
    rabbitmq_queue: str
    opensearch_index: str
    embedding_model: str
    embedding_base_url: str
    embedding_api_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            postgres_dsn=os.environ.get("POSTGRES_DSN", "postgresql://rag:rag@localhost:55432/rag"),
            rabbitmq_url=os.environ.get("RABBITMQ_URL", "amqp://rag:rag@localhost:5673/%2F"),
            opensearch_url=os.environ.get("OPENSEARCH_URL", "http://localhost:9201"),
            rabbitmq_queue=os.environ.get("RABBITMQ_QUEUE", "legal-ingest"),
            opensearch_index=os.environ.get("OPENSEARCH_INDEX", "legal-chunks"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3"),
            embedding_base_url=os.environ.get("EMBEDDING_BASE_URL", "https://openrouter.ai/api/v1"),
            embedding_api_key=os.environ.get("EMBEDDING_API_KEY", ""),
        )


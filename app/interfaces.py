from __future__ import annotations

from datetime import date
from typing import Protocol

from app.models import LegalDocument, SearchHit


class Embedder(Protocol):
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    def reset(self) -> None: ...
    def stage_version(self, version_id: str) -> int: ...
    def search(self, query: str, as_of: date, top_k: int) -> list[SearchHit]: ...


class ManifestRepository(Protocol):
    def reset(self) -> None: ...
    def register(self, document: LegalDocument) -> tuple[str, bool]: ...
    def active_version_ids(self, as_of: date) -> list[str]: ...


class EventBroker(Protocol):
    def publish_pending(self, duplicate_delivery: bool = False) -> int: ...
    def consume_all(self) -> dict[str, int]: ...


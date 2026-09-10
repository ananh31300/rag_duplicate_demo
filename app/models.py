from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LegalChunk:
    semantic_chunk_id: str
    text: str
    effective_from: date
    effective_to: date | None = None


@dataclass(frozen=True)
class LegalDocument:
    instrument_id: str
    number: str
    issued_date: date
    effective_from: date
    source_url: str
    chunks: tuple[LegalChunk, ...]
    amends_id: str | None = None


@dataclass(frozen=True)
class SearchHit:
    instrument_id: str
    version_id: str
    semantic_chunk_id: str
    text: str
    score: float
    effective_from: date
    effective_to: date | None


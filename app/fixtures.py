from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.models import LegalChunk, LegalDocument


def load_documents() -> tuple[LegalDocument, ...]:
    path = Path(__file__).parents[1] / "data" / "verified" / "documents.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents: list[LegalDocument] = []
    for item in payload:
        chunks = tuple(
            LegalChunk(
                semantic_chunk_id=chunk["semantic_chunk_id"],
                text=chunk["text"],
                effective_from=date.fromisoformat(chunk["effective_from"]),
                effective_to=date.fromisoformat(chunk["effective_to"]) if chunk.get("effective_to") else None,
            )
            for chunk in item["chunks"]
        )
        documents.append(LegalDocument(
            instrument_id=item["instrument_id"],
            number=item["number"],
            issued_date=date.fromisoformat(item["issued_date"]),
            effective_from=date.fromisoformat(item["effective_from"]),
            source_url=item["source_url"],
            chunks=chunks,
            amends_id=item.get("amends_id"),
        ))
    return tuple(documents)


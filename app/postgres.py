from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.models import LegalDocument
from app.normalization import content_hash, normalize_text


class PostgresManifest:
    def __init__(self, dsn: str, index_fingerprint: str = "hashing-v1") -> None:
        self._dsn = dsn
        self._index_fingerprint = index_fingerprint

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def reset(self) -> None:
        schema = (Path(__file__).parents[1] / "sql" / "schema.sql").read_text(encoding="utf-8")
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "DROP TABLE IF EXISTS processed_event, indexing_job, outbox_event, "
                "legal_chunk, document_version, legal_instrument CASCADE"
            )
            cursor.execute(schema)

    def register(self, document: LegalDocument) -> tuple[str, bool]:
        chunks = [
            {
                "semantic_chunk_id": chunk.semantic_chunk_id,
                "text": normalize_text(chunk.text),
                "effective_from": chunk.effective_from.isoformat(),
                "effective_to": chunk.effective_to.isoformat() if chunk.effective_to else None,
            }
            for chunk in document.chunks
        ]
        digest = content_hash(chunks)
        version_id = f"{document.instrument_id}:{digest[:12]}"
        operation_key = content_hash(
            {"instrument_id": document.instrument_id, "content_hash": digest, "index_fingerprint": self._index_fingerprint}
        )
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, operation_key))
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT active_version_id FROM legal_instrument WHERE instrument_id=%s",
                (document.instrument_id,),
            )
            active_row = cursor.fetchone()
            expected_active_version_id = active_row["active_version_id"] if active_row else None
            cursor.execute(
                """INSERT INTO legal_instrument
                   (instrument_id, normalized_number, issued_date, amends_id)
                   VALUES (%s, %s, %s, %s) ON CONFLICT (instrument_id) DO NOTHING""",
                (document.instrument_id, document.number, document.issued_date, document.amends_id),
            )
            cursor.execute(
                """INSERT INTO document_version
                   (version_id, instrument_id, content_hash, effective_from, source_url, status)
                   VALUES (%s, %s, %s, %s, %s, 'PREPARED')
                   ON CONFLICT (instrument_id, content_hash) DO NOTHING RETURNING version_id""",
                (version_id, document.instrument_id, digest, document.effective_from, document.source_url),
            )
            created = cursor.fetchone() is not None
            if not created:
                cursor.execute(
                    "SELECT version_id FROM document_version WHERE instrument_id=%s AND content_hash=%s",
                    (document.instrument_id, digest),
                )
                return str(cursor.fetchone()["version_id"]), False
            for chunk, normalized in zip(document.chunks, chunks):
                cursor.execute(
                    """INSERT INTO legal_chunk
                       (version_id, semantic_chunk_id, chunk_hash, text, effective_from, effective_to)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        version_id,
                        chunk.semantic_chunk_id,
                        content_hash(normalized["text"]),
                        normalized["text"],
                        chunk.effective_from,
                        chunk.effective_to,
                    ),
                )
            payload = {
                "event_id": event_id,
                "version_id": version_id,
                "operation_key": operation_key,
                "instrument_id": document.instrument_id,
                "expected_active_version_id": expected_active_version_id,
            }
            cursor.execute(
                """INSERT INTO outbox_event (event_id, aggregate_id, event_type, payload)
                   VALUES (%s, %s, 'LegalVersionPrepared', %s::jsonb)""",
                (event_id, document.instrument_id, json.dumps(payload)),
            )
        return version_id, True

    def active_version_ids(self, as_of: date) -> list[str]:
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT li.active_version_id FROM legal_instrument li
                   JOIN document_version dv ON dv.version_id=li.active_version_id
                   WHERE dv.effective_from <= %s""",
                (as_of,),
            )
            return [str(row["active_version_id"]) for row in cursor.fetchall()]

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        with self.connect() as connection, connection.cursor() as cursor:
            for name in ("legal_instrument", "document_version", "legal_chunk", "outbox_event"):
                cursor.execute(f"SELECT COUNT(*) AS count FROM {name}")
                result[name] = int(cursor.fetchone()["count"])
        return result


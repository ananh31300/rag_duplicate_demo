from __future__ import annotations

import json

import pika

from app.opensearch_store import OpenSearchVectorStore
from app.postgres import PostgresManifest


class RabbitOutboxBroker:
    def __init__(self, url: str, queue: str, manifest: PostgresManifest, store: OpenSearchVectorStore) -> None:
        self._parameters = pika.URLParameters(url)
        self._queue = queue
        self._manifest = manifest
        self._store = store

    def _channel(self) -> tuple[pika.BlockingConnection, object]:
        connection = pika.BlockingConnection(self._parameters)
        channel = connection.channel()
        channel.queue_declare(queue=self._queue, durable=True)
        channel.confirm_delivery()
        return connection, channel

    def purge(self) -> None:
        connection, channel = self._channel()
        channel.queue_purge(queue=self._queue)
        connection.close()

    def publish_pending(self, duplicate_delivery: bool = False) -> int:
        connection, channel = self._channel()
        published = 0
        with self._manifest.connect() as database, database.cursor() as cursor:
            cursor.execute(
                """SELECT event_id, payload FROM outbox_event WHERE published_at IS NULL
                   ORDER BY created_at FOR UPDATE SKIP LOCKED"""
            )
            for row in cursor.fetchall():
                body = json.dumps(row["payload"]).encode("utf-8")
                for _ in range(2 if duplicate_delivery else 1):
                    channel.basic_publish(
                        exchange="",
                        routing_key=self._queue,
                        body=body,
                        properties=pika.BasicProperties(
                            delivery_mode=pika.DeliveryMode.Persistent,
                            content_type="application/json",
                            message_id=row["event_id"],
                        ),
                        mandatory=True,
                    )
                    published += 1
                cursor.execute("UPDATE outbox_event SET published_at=NOW() WHERE event_id=%s", (row["event_id"],))
        connection.close()
        return published

    def consume_all(self) -> dict[str, int]:
        connection, channel = self._channel()
        processed = 0
        duplicates = 0
        while True:
            method, _, body = channel.basic_get(queue=self._queue, auto_ack=False)
            if method is None:
                break
            payload = json.loads(body)
            try:
                if self._process(payload):
                    processed += 1
                else:
                    duplicates += 1
                channel.basic_ack(delivery_tag=method.delivery_tag)
            except (pika.exceptions.AMQPError, RuntimeError):
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                connection.close()
                raise
        connection.close()
        return {"processed": processed, "duplicate_deliveries": duplicates}

    def _process(self, payload: dict[str, str]) -> bool:
        event_id = payload["event_id"]
        operation_key = payload["operation_key"]
        version_id = payload["version_id"]
        with self._manifest.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM processed_event WHERE event_id=%s", (event_id,))
            if cursor.fetchone() is not None:
                return False
            cursor.execute(
                """INSERT INTO indexing_job (operation_key, version_id, status)
                   VALUES (%s, %s, 'INDEXING')
                   ON CONFLICT (operation_key) DO UPDATE SET updated_at=NOW()""",
                (operation_key, version_id),
            )
        indexed = self._store.stage_version(version_id)
        if indexed == 0:
            raise RuntimeError(f"Version {version_id} has no chunks")
        with self._manifest.connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE document_version SET status='VALIDATED' WHERE version_id=%s", (version_id,))
            cursor.execute(
                """UPDATE document_version SET status='RETIRED'
                   WHERE instrument_id=%s AND status='ACTIVE' AND version_id<>%s""",
                (payload["instrument_id"], version_id),
            )
            cursor.execute(
                """UPDATE legal_instrument SET active_version_id=%s
                   WHERE instrument_id=%s AND active_version_id IS NOT DISTINCT FROM %s
                   RETURNING instrument_id""",
                (version_id, payload["instrument_id"], payload.get("expected_active_version_id")),
            )
            if cursor.fetchone() is None:
                raise RuntimeError(f"CAS activation rejected stale event for {payload['instrument_id']}")
            cursor.execute("UPDATE document_version SET status='ACTIVE' WHERE version_id=%s", (version_id,))
            cursor.execute(
                """UPDATE indexing_job SET status='COMPLETED', indexed_chunks=%s, updated_at=NOW()
                   WHERE operation_key=%s""",
                (indexed, operation_key),
            )
            cursor.execute("INSERT INTO processed_event (event_id) VALUES (%s)", (event_id,))
        return True


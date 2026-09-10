from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.broker import RabbitOutboxBroker
from app.config import Settings
from app.fixtures import load_documents
from app.embedding import OpenRouterEmbedder, OpenRouterEmbeddingConfig
from app.opensearch_store import OpenSearchVectorStore
from app.postgres import PostgresManifest


def run_all(settings: Settings) -> dict[str, object]:
    manifest = PostgresManifest(settings.postgres_dsn, settings.embedding_model)
    embedder = OpenRouterEmbedder(OpenRouterEmbeddingConfig(
        model=settings.embedding_model,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
    ))
    store = OpenSearchVectorStore(settings.opensearch_url, settings.opensearch_index, manifest, embedder)
    broker = RabbitOutboxBroker(settings.rabbitmq_url, settings.rabbitmq_queue, manifest, store)
    manifest.reset()
    store.reset()
    broker.purge()
    nd118, nd309 = load_documents()
    started = time.monotonic()
    version_118, created_118 = manifest.register(nd118)
    first_publish = broker.publish_pending(duplicate_delivery=True)
    first_consume = broker.consume_all()
    before_hits = store.search("ki-ốt thông minh xác thực danh tính VNeID", date(2026, 8, 4), 3)
    counts_before = manifest.counts()
    same_version, duplicate_created = manifest.register(nd118)
    counts_after = manifest.counts()
    version_309, created_309 = manifest.register(nd309)
    second_publish = broker.publish_pending(duplicate_delivery=True)
    second_consume = broker.consume_all()
    after_hits = store.search("ki-ốt thông minh xác thực danh tính VNeID", date(2026, 8, 6), 3)
    as_of = date(2026, 8, 6)
    stale = [hit for hit in after_hits if hit.effective_from > as_of or (hit.effective_to and hit.effective_to <= as_of)]
    leakage = len(stale) / len(after_hits) if after_hits else None
    assertions = {
        "first_version_created": created_118,
        "same_input_returns_same_version": same_version == version_118,
        "same_input_did_not_create_new_version": not duplicate_created,
        "manifest_unchanged_after_duplicate": counts_before == counts_after,
        "amending_instrument_created": created_309,
        "duplicate_delivery_deduplicated": first_consume["duplicate_deliveries"] == 1 and second_consume["duplicate_deliveries"] == 1,
        "kiosk_not_retrieved_before_effective_date": all(hit.instrument_id != "nd309-2026" for hit in before_hits),
        "kiosk_retrieved_after_effective_date": any(hit.semantic_chunk_id == "nd118/dieu-17/khoan-2a" for hit in after_hits),
    }
    report: dict[str, object] = {
        "fixture_scope": "verified metadata with shortened legal excerpts",
        "embedding_adapter": embedder.name,
        "versions": {"nd118": version_118, "nd309": version_309},
        "assertions": assertions,
        "metrics": {
            "published_messages": first_publish + second_publish,
            "processed_events": first_consume["processed"] + second_consume["processed"],
            "duplicate_deliveries": first_consume["duplicate_deliveries"] + second_consume["duplicate_deliveries"],
            "manifest_counts": manifest.counts(),
            "opensearch_document_count": store.document_count(),
            "returned_chunks_after_update": len(after_hits),
            "stale_matching_leakage": leakage,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        },
        "query_before_effective_date": [asdict(hit) for hit in before_hits],
        "query_after_effective_date": [asdict(hit) for hit in after_hits],
    }
    failed = [name for name, passed in assertions.items() if not passed]
    if failed:
        raise RuntimeError(f"Demo assertions failed: {failed}")
    return report


def write_report(report: dict[str, object]) -> None:
    artifact_dir = Path(__file__).parents[1] / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    (artifact_dir / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    metrics = report["metrics"]
    assertions = report["assertions"]
    lines = ["# Kết quả demo", "", f"- Embedding adapter: `{report['embedding_adapter']}`", f"- OpenSearch documents: {metrics['opensearch_document_count']}", f"- Duplicate deliveries: {metrics['duplicate_deliveries']}", f"- Stale matching leakage: {metrics['stale_matching_leakage']}", f"- Elapsed: {metrics['elapsed_ms']} ms", "", "## Assertions", ""]
    lines.extend(f"- [{'x' if passed else ' '}] `{name}`" for name, passed in assertions.items())
    (artifact_dir / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.demo import run_all


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    """Run the paid/networked integration scenario once for this module."""
    return run_all(Settings.from_env())


def test_transactional_outbox_has_one_event_per_new_version(
    report: dict[str, Any],
) -> None:
    counts = report["metrics"]["manifest_counts"]

    assert counts["document_version"] == 2
    assert counts["outbox_event"] == 2


def test_same_input_is_idempotent(report: dict[str, Any]) -> None:
    assertions = report["assertions"]

    assert assertions["same_input_returns_same_version"] is True
    assert assertions["same_input_did_not_create_new_version"] is True
    assert assertions["manifest_unchanged_after_duplicate"] is True


def test_rabbitmq_redelivery_is_processed_once(report: dict[str, Any]) -> None:
    metrics = report["metrics"]

    assert metrics["published_messages"] == 4
    assert metrics["processed_events"] == 2
    assert metrics["duplicate_deliveries"] == 2


def test_opensearch_has_no_duplicate_chunk_documents(
    report: dict[str, Any],
) -> None:
    metrics = report["metrics"]

    assert metrics["manifest_counts"]["legal_chunk"] == 4
    assert metrics["opensearch_document_count"] == 4


def test_amendment_is_hidden_before_effective_date(
    report: dict[str, Any],
) -> None:
    hits = report["query_before_effective_date"]

    assert hits
    assert all(hit["instrument_id"] != "nd309-2026" for hit in hits)


def test_amendment_is_retrieved_after_effective_date(
    report: dict[str, Any],
) -> None:
    hits = report["query_after_effective_date"]

    assert hits[0]["semantic_chunk_id"] == "nd118/dieu-17/khoan-2a"
    assert hits[0]["instrument_id"] == "nd309-2026"
    assert "VNeID" in hits[0]["text"]


def test_stale_matching_leakage_is_zero_for_fixture(
    report: dict[str, Any],
) -> None:
    metrics = report["metrics"]

    assert metrics["returned_chunks_after_update"] == 3
    assert metrics["stale_matching_leakage"] == 0.0


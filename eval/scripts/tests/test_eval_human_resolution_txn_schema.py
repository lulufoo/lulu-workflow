#!/usr/bin/env python3
"""Tests for Human Resolution transaction journal schema."""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_human_resolution_txn_schema import (  # noqa: E402
    HUMAN_RESOLUTION_TXN_VERSION,
    load_human_resolution_txn,
    save_human_resolution_txn,
    validate_human_resolution_txn,
)


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _transaction() -> dict:
    targets = {}
    for name in ("review_file", "evaluate_state", "operation_records"):
        before = f"{name}-before"
        after = f"{name}-after"
        targets[name] = {
            "path": f"/tmp/{name}",
            "before": before,
            "before_digest": _digest(before),
            "after": after,
            "after_digest": _digest(after),
        }
    return {
        "version": HUMAN_RESOLUTION_TXN_VERSION,
        "operation": "submit-human-resolution",
        "dimension_token": "token-1",
        "submission_digest": "a" * 64,
        "phase": "prepared",
        "targets": targets,
    }


def test_round_trip(tmp_path: Path):
    path = tmp_path / "_human-resolution-txn.json"
    transaction = _transaction()
    save_human_resolution_txn(path, transaction)
    assert load_human_resolution_txn(path) == transaction


def test_rejects_missing_target():
    transaction = _transaction()
    del transaction["targets"]["evaluate_state"]
    assert any(
        "targets must contain" in error
        for error in validate_human_resolution_txn(transaction)
    )

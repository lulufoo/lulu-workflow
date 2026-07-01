#!/usr/bin/env python3
"""Tests for lulu-plan human_delivery_gate_schema.py."""

import json
import sys
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from bootstrap import CORE, SCHEMA_SESSION  # noqa: E402

from human_delivery_gate_schema import (
    delivery_gate_exists,
    get_schema,
    load_delivery_gate,
    validate_delivery_gate,
    write_approved,
)


class TestGetSchema:
    def test_required_fields(self):
        required = {s["field"] for s in get_schema() if s["required"]}
        assert required == {"approved", "approved_at"}


class TestValidateDeliveryGate:
    def test_valid(self):
        assert validate_delivery_gate({
            "approved": "true",
            "approved_at": "2024-01-01T00:00:00+00:00",
        }) == []

    def test_missing_approved(self):
        errors = validate_delivery_gate({"approved_at": "2024-01-01T00:00:00+00:00"})
        assert any("approved" in e for e in errors)


class TestWriteApproved:
    def test_writes_valid_gate(self, tmp_path: Path):
        path = tmp_path / "human-delivery-gate.md"
        write_approved(path, note="User confirmed delivery.")
        loaded = load_delivery_gate(path)
        assert loaded["approved"] == "true"
        assert loaded["note"] == "User confirmed delivery."

    def test_delivery_gate_exists(self, tmp_path: Path):
        path = tmp_path / "human-delivery-gate.md"
        assert delivery_gate_exists(path) is False
        write_approved(path)
        assert delivery_gate_exists(path) is True


class TestCli:
    def test_schema_flag(self):
        import subprocess

        script = SCHEMA_SESSION / "human_delivery_gate_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--schema"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)

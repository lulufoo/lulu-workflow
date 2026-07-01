#!/usr/bin/env python3
"""Schema and I/O for decision gate-payloads/<G>.json files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dec_io import atomic_write_text


def gate_payload_path(payloads_dir: Path, gate: str) -> Path:
    return payloads_dir / f"{gate}.json"


def save_gate_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )


def load_gate_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"gate payload not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"gate payload must be an object: {path}")
    return data


def delete_gate_payload(path: Path) -> None:
    if path.exists():
        path.unlink()


def delete_payloads_from(payloads_dir: Path, gate: str, gate_order: tuple[str, ...]) -> None:
    if gate not in gate_order:
        raise ValueError(f"invalid gate: {gate!r}")
    start = gate_order.index(gate)
    for downstream in gate_order[start:]:
        delete_gate_payload(gate_payload_path(payloads_dir, downstream))


def gate_payloads_for_session(payloads_dir: Path) -> dict[str, dict[str, Any]]:
    if not payloads_dir.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(payloads_dir.glob("*.json")):
        gate = path.stem
        result[gate] = load_gate_payload(path)
    return result

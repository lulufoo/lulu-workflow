#!/usr/bin/env python3
"""Schema and I/O for diagnostic registers.json."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dx_io import atomic_write_text

PRIOR_KINDS = frozenset({"judgment", "preference", "concern", "excluded"})
REGISTER_STATES = frozenset({"pending", "verified", "invalidated"})
REGISTER_SOURCES = frozenset({"O", "Q", "E", "D", "X", "R", "V", "RR"})
RISK_LEVELS = frozenset({"H", "M", "L"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def init_registers(*, cycle_id: str, stage: str) -> dict[str, Any]:
    return normalize_registers(
        {
            "version": "1",
            "cycle_id": cycle_id,
            "stage": stage,
            "prior": [],
            "assumptions": [],
            "next_prior_seq": 1,
            "next_assumption_seq": 1,
            "updated_at": _now_iso(),
        }
    )


def validate_registers(data: dict[str, Any], *, r_gate_closed: bool = False) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    prior = data.get("prior")
    if not isinstance(prior, list):
        errors.append("prior must be an array")
    else:
        seen_prior: set[str] = set()
        for index, entry in enumerate(prior):
            errors.extend(_validate_prior_entry(entry, index, seen_prior))

    assumptions = data.get("assumptions")
    if not isinstance(assumptions, list):
        errors.append("assumptions must be an array")
    else:
        seen_assumption: set[str] = set()
        for index, entry in enumerate(assumptions):
            errors.extend(
                _validate_assumption_entry(entry, index, seen_assumption, r_gate_closed=r_gate_closed)
            )

    return errors


def _validate_prior_entry(entry: Any, index: int, seen: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"prior[{index}] must be an object"]
    entry_id = str(entry.get("id", ""))
    if not re.fullmatch(r"P\d+", entry_id):
        errors.append(f"prior[{index}].id invalid: {entry_id!r}")
    elif entry_id in seen:
        errors.append(f"duplicate prior id: {entry_id}")
    else:
        seen.add(entry_id)

    kind = str(entry.get("kind", ""))
    if kind not in PRIOR_KINDS:
        errors.append(f"prior[{index}].kind invalid: {kind!r}")

    state = str(entry.get("state", ""))
    if state not in REGISTER_STATES:
        errors.append(f"prior[{index}].state invalid: {state!r}")

    source = str(entry.get("source", ""))
    if source not in REGISTER_SOURCES:
        errors.append(f"prior[{index}].source invalid: {source!r}")

    if not str(entry.get("text", "")).strip():
        errors.append(f"prior[{index}].text must be non-empty")
    return errors


def _validate_assumption_entry(
    entry: Any,
    index: int,
    seen: set[str],
    *,
    r_gate_closed: bool,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"assumptions[{index}] must be an object"]
    entry_id = str(entry.get("id", ""))
    if not re.fullmatch(r"A\d+", entry_id):
        errors.append(f"assumptions[{index}].id invalid: {entry_id!r}")
    elif entry_id in seen:
        errors.append(f"duplicate assumption id: {entry_id}")
    else:
        seen.add(entry_id)

    state = str(entry.get("state", ""))
    if state not in REGISTER_STATES:
        errors.append(f"assumptions[{index}].state invalid: {state!r}")

    source = str(entry.get("source", ""))
    if source not in REGISTER_SOURCES:
        errors.append(f"assumptions[{index}].source invalid: {source!r}")

    if not str(entry.get("text", "")).strip():
        errors.append(f"assumptions[{index}].text must be non-empty")

    risk = entry.get("risk")
    if risk is not None:
        risk_s = str(risk)
        if risk_s not in RISK_LEVELS:
            errors.append(f"assumptions[{index}].risk invalid: {risk_s!r}")
        elif not r_gate_closed:
            errors.append(f"assumptions[{index}].risk set before R gate closed")

    return errors


def normalize_registers(data: dict[str, Any]) -> dict[str, Any]:
    prior_raw = data.get("prior")
    assumptions_raw = data.get("assumptions")
    prior = prior_raw if isinstance(prior_raw, list) else []
    assumptions = assumptions_raw if isinstance(assumptions_raw, list) else []

    for entry in prior:
        if isinstance(entry, dict) and str(entry.get("source", "")) == "open":
            entry["source"] = "O"
    for entry in assumptions:
        if isinstance(entry, dict) and str(entry.get("source", "")) == "open":
            entry["source"] = "O"

    return {
        "version": "1",
        "cycle_id": str(data.get("cycle_id", "")),
        "stage": str(data.get("stage", "")),
        "prior": prior,
        "assumptions": assumptions,
        "next_prior_seq": int(data.get("next_prior_seq", 1)),
        "next_assumption_seq": int(data.get("next_assumption_seq", 1)),
        "updated_at": data.get("updated_at") or _now_iso(),
    }


def load_registers(path: Path, *, r_gate_closed: bool = False) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"registers not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    normalized = normalize_registers(data)
    errors = validate_registers(normalized, r_gate_closed=r_gate_closed)
    if errors:
        raise ValueError("; ".join(errors))
    return normalized


def save_registers(path: Path, data: dict[str, Any], *, r_gate_closed: bool = False) -> None:
    normalized = normalize_registers(data)
    errors = validate_registers(normalized, r_gate_closed=r_gate_closed)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized["updated_at"] = _now_iso()
    atomic_write_text(
        path,
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
    )


def next_prior_id(data: dict[str, Any]) -> str:
    seq = int(data.get("next_prior_seq", 1))
    return f"P{seq}"


def next_assumption_id(data: dict[str, Any]) -> str:
    seq = int(data.get("next_assumption_seq", 1))
    return f"A{seq}"


def find_duplicate_prior(data: dict[str, Any], *, kind: str, text: str) -> dict[str, Any] | None:
    target = _normalize_text(text)
    for entry in data.get("prior", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("kind", "")) == kind and _normalize_text(str(entry.get("text", ""))) == target:
            return entry
    return None


def find_duplicate_assumption(data: dict[str, Any], text: str) -> dict[str, Any] | None:
    target = _normalize_text(text)
    for entry in data.get("assumptions", []):
        if not isinstance(entry, dict):
            continue
        if _normalize_text(str(entry.get("text", ""))) == target:
            return entry
    return None


def header_state_symbol(state: str) -> str:
    return "✓" if state == "verified" else "?"


def format_prior_header_line(entry: dict[str, Any]) -> str:
    state = header_state_symbol(str(entry.get("state", "pending")))
    source = str(entry.get("source", ""))
    return f"[{entry.get('id')}{state} {source}] {entry.get('text')}"


def format_assumption_header_line(entry: dict[str, Any]) -> str:
    state = header_state_symbol(str(entry.get("state", "pending")))
    source = str(entry.get("source", ""))
    risk = entry.get("risk")
    risk_part = f" {risk}" if risk else ""
    return f"[{entry.get('id')}{state} {source}{risk_part}] {entry.get('text')}"

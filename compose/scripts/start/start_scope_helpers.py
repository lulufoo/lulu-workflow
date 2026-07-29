#!/usr/bin/env python3
"""Shared scope-ref selection helpers for StartAdapter implementations."""

from __future__ import annotations

import json
from pathlib import Path

from delivered_refs_schema import (
    DeliveredRef,
)


def first_ref(refs: list[DeliveredRef], delivered_type: str) -> DeliveredRef | None:
    for ref in refs:
        if ref.type == delivered_type:
            return ref
    return None


class DecisionFactScopeError(ValueError):
    """decision_fact_path missing, unusable, or has no units — compose will not use prose path."""


def _load_decision_fact_for_scope(path: Path | str) -> dict:
    """Load decision-fact.json for scope selection; raise if path is broken."""
    p = Path(path)
    if not p.is_file():
        raise DecisionFactScopeError(
            f"decision_fact_path missing or not a file: {p}"
        )
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecisionFactScopeError(
            f"decision_fact_path unreadable/corrupt: {p} ({exc})"
        ) from exc
    if not isinstance(data, dict):
        raise DecisionFactScopeError(
            f"decision_fact_path must be a JSON object: {p}"
        )
    gates = data.get("gates")
    if gates is None:
        raise DecisionFactScopeError(
            f"decision_fact_path missing gates object: {p}"
        )
    if not isinstance(gates, dict):
        raise DecisionFactScopeError(
            f"decision_fact_path.gates must be an object: {p}"
        )
    return data


def decision_fact_has_units(path: Path | str) -> bool:
    """True when path is a readable decision-fact.json with at least one unit (id+text).

    Raises ``DecisionFactScopeError`` when the path is missing/corrupt.
    """
    data = _load_decision_fact_for_scope(path)
    gates = data["gates"]
    if not isinstance(gates, dict) or not gates:
        return False
    for units in gates.values():
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            if str(unit.get("id", "")).strip() and str(unit.get("text", "")).strip():
                return True
    return False


def _is_decision_package_filename(path: Path | str) -> bool:
    return Path(path).name == "decision-package.json"


def require_decision_fact_scope(ref: DeliveredRef) -> DeliveredRef:
    """Return compose scope SSOT: ``decision_fact_path`` with ≥1 unit (id+text).

    Cycle ``entry.path`` (decision-doc) stays on the delivered entry for human/eval;
    compose ``scope_ref.path`` / ``$SCOPE_REF`` **must** be the fact file.

    No prose fallback: missing ``decision_fact_path``, unreadable fact, empty
    ``gates``, or zero units → ``DecisionFactScopeError``.
    Rejects ``decision-package.json`` as ``$SCOPE_REF`` (P3 isolation).
    """
    if _is_decision_package_filename(ref.path):
        raise DecisionFactScopeError(
            "decision-package.json must not be used as $SCOPE_REF; "
            "project to scope-package.json first"
        )
    fact_raw = str(ref.decision_fact_path or "").strip()
    if not fact_raw:
        raise DecisionFactScopeError(
            f"decision_fact_path required on delivered-refs[{ref.type}] "
            "(compose does not use prose entry.path as scope)"
        )
    if _is_decision_package_filename(fact_raw):
        raise DecisionFactScopeError(
            "decision-package.json must not be used as $SCOPE_REF; "
            "project to scope-package.json first"
        )
    if not decision_fact_has_units(fact_raw):
        raise DecisionFactScopeError(
            f"decision_fact_path has no units (id+text): {fact_raw}"
        )
    return DeliveredRef(
        type=ref.type,
        path=str(Path(fact_raw).resolve()),
    )


# Backward-compatible name used by older call sites / docs.
prefer_decision_fact_scope = require_decision_fact_scope

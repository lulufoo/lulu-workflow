#!/usr/bin/env python3
"""Claim / orphan ledger for decision-fact units (compose consumer side).

Step 3 SoT: tracks every unit id from decision-fact.json as
unclaimed | claimed | settled | deferred. Missing decision-fact → prose_fallback.
Does not import units into facts (consumption is a later step).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLAIM_FILE = "decision-fact-claims.json"
CLAIM_VERSION = 1
CLAIM_STATUSES = frozenset({"unclaimed", "claimed", "settled", "deferred"})
CLAIM_MODES = frozenset({"units", "prose_fallback"})


def claim_ledger_path(revision_dir: Path) -> Path:
    return revision_dir / CLAIM_FILE


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def flatten_unit_ids(fact: dict[str, Any]) -> list[str]:
    """Stable-ordered unit ids from decision-fact.json gates."""
    gates = fact.get("gates")
    if not isinstance(gates, dict):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for gate in sorted(gates.keys()):
        units = gates.get(gate)
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            unit_id = str(unit.get("id", "")).strip()
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            ids.append(unit_id)
    return ids


def load_decision_fact_units(path: Path) -> dict[str, Any]:
    """Load decision-fact.json (producer artifact) for claim sync."""
    if not path.is_file():
        raise FileNotFoundError(f"decision-fact not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"decision-fact must be an object: {path}")
    gates = data.get("gates")
    if not isinstance(gates, dict):
        raise ValueError(f"decision-fact.gates must be an object: {path}")
    return data


def empty_unit_entry(status: str = "unclaimed") -> dict[str, str]:
    return {"status": status, "by": "", "note": ""}


def build_prose_fallback_ledger(*, source_ref: str = "") -> dict[str, Any]:
    return {
        "version": CLAIM_VERSION,
        "source_ref": source_ref,
        "mode": "prose_fallback",
        "units": {},
        "orphan_ids": [],
        "updated_at": _now_iso(),
    }


def build_units_ledger(
    unit_ids: list[str],
    *,
    source_ref: str,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build/sync units ledger; preserve prior status for surviving ids."""
    prev_units: dict[str, Any] = {}
    if isinstance(previous, dict) and previous.get("mode") == "units":
        raw = previous.get("units")
        if isinstance(raw, dict):
            prev_units = raw

    units: dict[str, Any] = {}
    for unit_id in unit_ids:
        prior = prev_units.get(unit_id)
        if isinstance(prior, dict) and str(prior.get("status", "")) in CLAIM_STATUSES:
            units[unit_id] = {
                "status": str(prior["status"]),
                "by": str(prior.get("by", "")),
                "note": str(prior.get("note", "")),
            }
        else:
            units[unit_id] = empty_unit_entry("unclaimed")

    stale = sorted(set(prev_units) - set(unit_ids))
    return {
        "version": CLAIM_VERSION,
        "source_ref": source_ref,
        "mode": "units",
        "units": units,
        "orphan_ids": stale,
        "updated_at": _now_iso(),
    }


def validate_claim_ledger(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["claim ledger must be an object"]
    if data.get("version") != CLAIM_VERSION:
        errors.append(f"invalid version: {data.get('version')!r}")
    mode = str(data.get("mode", "")).strip()
    if mode not in CLAIM_MODES:
        errors.append(f"invalid mode: {mode!r}")
    units = data.get("units")
    if not isinstance(units, dict):
        errors.append("units must be an object")
        return errors
    if mode == "prose_fallback" and units:
        errors.append("prose_fallback ledger must have empty units")
    for unit_id, entry in units.items():
        if not str(unit_id).strip():
            errors.append("units contains empty id")
            continue
        if not isinstance(entry, dict):
            errors.append(f"units.{unit_id} must be an object")
            continue
        status = str(entry.get("status", "")).strip()
        if status not in CLAIM_STATUSES:
            errors.append(f"units.{unit_id}.status invalid: {status!r}")
    orphans = data.get("orphan_ids")
    if orphans is None:
        pass
    elif not isinstance(orphans, list):
        errors.append("orphan_ids must be an array")
    else:
        for item in orphans:
            if not str(item).strip():
                errors.append("orphan_ids contains empty id")
    return errors


def load_claim_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"claim ledger not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"claim ledger must be an object: {path}")
    errors = validate_claim_ledger(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def save_claim_ledger(path: Path, data: dict[str, Any]) -> None:
    errors = validate_claim_ledger(data)
    if errors:
        raise ValueError("; ".join(errors))
    _atomic_write_text(
        path,
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    )


def _validate_units_min(fact: dict[str, Any]) -> list[str]:
    """Minimal consumer contract: every unit has unique non-empty id + text."""
    errors: list[str] = []
    gates = fact.get("gates")
    if not isinstance(gates, dict):
        return ["decision-fact.gates must be an object"]
    seen: set[str] = set()
    for gate, units in gates.items():
        if not isinstance(units, list):
            errors.append(f"gates.{gate} must be an array")
            continue
        for index, unit in enumerate(units):
            if not isinstance(unit, dict):
                errors.append(f"gates.{gate}[{index}] must be an object")
                continue
            unit_id = str(unit.get("id", "")).strip()
            text = str(unit.get("text", "")).strip()
            if not unit_id:
                errors.append(f"gates.{gate}[{index}].id is required")
            elif unit_id in seen:
                errors.append(f"duplicate unit id: {unit_id}")
            else:
                seen.add(unit_id)
            if not text:
                errors.append(f"gates.{gate}[{index}].text is required")
    return errors


def ensure_claim_ledger(
    revision_dir: Path,
    *,
    decision_fact_path: str | None,
) -> dict[str, Any]:
    """Create or sync ledger from optional decision-fact path.

    - Missing fact + no prior units ledger → ``prose_fallback``.
    - Missing / unreadable fact when prior mode is ``units`` → hard-fail (never wipe).
    - Corrupt existing ledger → hard-fail (never silent rebuild).
    - Present decision-fact (including empty ``gates``) → always ``mode=units``;
      never downgrade an existing units ledger to prose_fallback.
    """
    path = claim_ledger_path(revision_dir)
    previous: dict[str, Any] | None = None
    if path.is_file():
        previous = load_claim_ledger(path)

    fact_raw = str(decision_fact_path or "").strip()
    prior_units = (
        isinstance(previous, dict)
        and str(previous.get("mode", "")).strip() == "units"
    )

    if not fact_raw or not Path(fact_raw).is_file():
        if prior_units:
            raise ValueError(
                "decision-fact missing/unreadable while claim ledger is in units "
                f"mode (refusing to wipe): {fact_raw or '(empty)'}"
            )
        ledger = build_prose_fallback_ledger(source_ref=fact_raw)
        save_claim_ledger(path, ledger)
        return ledger

    fact = load_decision_fact_units(Path(fact_raw))
    unit_errors = _validate_units_min(fact)
    if unit_errors:
        raise ValueError(
            "decision-fact failed claim contract: " + "; ".join(unit_errors)
        )

    unit_ids = flatten_unit_ids(fact)
    # Empty gates/units stay mode=units (D6 still applies; all prior ids → stale).
    ledger = build_units_ledger(
        unit_ids,
        source_ref=str(Path(fact_raw).resolve()),
        previous=previous,
    )
    save_claim_ledger(path, ledger)
    return ledger


def claim_report(ledger: dict[str, Any]) -> dict[str, Any]:
    """Summarize claim statuses; unclaimed is the explicit orphan exposure (D6)."""
    mode = str(ledger.get("mode", "")).strip()
    if mode == "prose_fallback":
        return {
            "mode": mode,
            "source_ref": str(ledger.get("source_ref", "")),
            "unclaimed": [],
            "claimed": [],
            "settled": [],
            "deferred": [],
            "stale_orphan_ids": list(ledger.get("orphan_ids") or []),
            "ok": True,
        }

    buckets: dict[str, list[str]] = {
        "unclaimed": [],
        "claimed": [],
        "settled": [],
        "deferred": [],
    }
    units = ledger.get("units") if isinstance(ledger.get("units"), dict) else {}
    for unit_id, entry in sorted(units.items()):
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "")).strip()
        if status in buckets:
            buckets[status].append(str(unit_id))

    return {
        "mode": mode,
        "source_ref": str(ledger.get("source_ref", "")),
        **buckets,
        "stale_orphan_ids": [str(x) for x in (ledger.get("orphan_ids") or [])],
        "ok": True,
    }


def evaluate_claim_gate(
    ledger: dict[str, Any],
    *,
    fail_on_unclaimed: bool = False,
) -> dict[str, Any]:
    """D6 / §5.3 gate predicate over a claim ledger.

    - ``prose_fallback``: always gate_ok.
    - ``units``: unclaimed is a valid terminal state (orphan exposure); claimed must
      be settled∨deferred (fail while still ``claimed``); stale source ids fail.
    - ``fail_on_unclaimed``: optional stricter policy (not the D6 default).
    """
    report = claim_report(ledger)
    errors: list[str] = []
    gate_ok = True
    orphan_exposed = list(report.get("unclaimed") or [])

    if report["mode"] == "units":
        claimed = list(report.get("claimed") or [])
        stale = list(report.get("stale_orphan_ids") or [])
        if claimed:
            gate_ok = False
            errors.append(
                f"{len(claimed)} claimed-but-open unit(s) "
                f"(must be settled∨deferred): " + ", ".join(claimed)
            )
        if stale:
            gate_ok = False
            errors.append(
                f"{len(stale)} stale id(s) removed from source: " + ", ".join(stale)
            )
        if fail_on_unclaimed and orphan_exposed:
            gate_ok = False
            errors.append(
                f"{len(orphan_exposed)} unclaimed unit(s): "
                + ", ".join(orphan_exposed)
            )

    return {
        **report,
        "gate_ok": gate_ok,
        "orphan_exposed": orphan_exposed,
        "errors": errors,
        "ok": gate_ok,
    }


def sync_and_evaluate_claims(
    revision_dir: Path,
    *,
    decision_fact_path: str | None,
    fail_on_unclaimed: bool = False,
) -> dict[str, Any]:
    """Ensure ledger from source, then evaluate the D6 gate."""
    ledger = ensure_claim_ledger(
        revision_dir,
        decision_fact_path=decision_fact_path,
    )
    result = evaluate_claim_gate(ledger, fail_on_unclaimed=fail_on_unclaimed)
    result["ledger_path"] = claim_ledger_path(revision_dir).as_posix()
    return result


def set_unit_status(
    revision_dir: Path,
    unit_id: str,
    status: str,
    *,
    by: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Update one unit's claim status (Seed/Init co-batch with fact write)."""
    status_norm = str(status).strip()
    if status_norm not in CLAIM_STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    unit_key = str(unit_id).strip()
    if not unit_key:
        raise ValueError("unit_id must be non-empty")

    path = claim_ledger_path(revision_dir)
    ledger = load_claim_ledger(path)
    if str(ledger.get("mode", "")).strip() != "units":
        raise ValueError("cannot set-status when ledger mode is not units")
    units = ledger.get("units")
    if not isinstance(units, dict) or unit_key not in units:
        raise ValueError(f"unknown unit id: {unit_key}")
    entry = units.get(unit_key)
    if not isinstance(entry, dict):
        raise ValueError(f"units.{unit_key} must be an object")
    updated = {
        "status": status_norm,
        "by": str(by).strip() if str(by).strip() else str(entry.get("by", "")),
        "note": str(note).strip() if str(note).strip() else str(entry.get("note", "")),
    }
    units[unit_key] = updated
    ledger["units"] = units
    ledger["updated_at"] = _now_iso()
    save_claim_ledger(path, ledger)
    return ledger

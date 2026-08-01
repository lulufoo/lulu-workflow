#!/usr/bin/env python3
"""Schema and I/O for decision-fact.json (atomized gate/register units).

Cross-stage contract: each unit has stable ``id`` + readable ``text``.
Optional ``slot`` is producer rematch metadata (consumers may ignore).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from dec_gate_payload_schema import gate_payloads_for_session
from dec_io import atomic_write_text

DECISION_FACT_FILENAME = "decision-fact.json"
DECISION_FACT_VERSION = 1

# Content-bearing gates only (O/DC/V/RR are control; assumptions live in registers).
_GATE_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "Q": ("problem_statement", "constraints"),
    "E": ("user_choice",),
    "D": ("decision_rationale", "applies_to", "excludes", "execution_approach"),
    "X": (
        "acceptance_criteria",
        "gap",
        "key_changes",
        "critical_constraints",
        "reversibility",
    ),
    "R": ("exit", "realign_gate"),
}

_GATE_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "GL": ("exchanges",),
    "E": ("directions", "excluded"),
    "X": ("impact_surface", "external_dependencies"),
}

_LIST_ITEM_KEYS: dict[str, tuple[str, ...]] = {
    "exchanges": ("lens", "question", "answer", "na"),
    "directions": ("name", "approach", "pros", "cons", "recommended"),
    "excluded": ("name", "reason"),
    "impact_surface": ("layer", "area", "change_type", "notes"),
    "external_dependencies": ("dependency", "contract", "source", "confirmation"),
}


def decision_fact_filename() -> str:
    return DECISION_FACT_FILENAME


def decision_fact_path(session_dir: Path) -> Path:
    return session_dir / DECISION_FACT_FILENAME


def _mint_ids(units: list[dict[str, Any]], id_prefix: str) -> list[dict[str, Any]]:
    """Assign ``<prefix>-<n>`` ids to units without one; keep explicit ids as-is."""
    prefix = str(id_prefix).strip()
    used: set[int] = set()
    for unit in units:
        raw = str(unit.get("id", "")).strip()
        if raw.startswith(f"{prefix}-"):
            suffix = raw[len(prefix) + 1 :]
            if suffix.isdigit():
                used.add(int(suffix))

    minted: list[dict[str, Any]] = []
    counter = 0
    for unit in units:
        out = {k: v for k, v in unit.items()}
        raw = str(out.get("id", "")).strip()
        if not raw:
            counter += 1
            while counter in used:
                counter += 1
            used.add(counter)
            out["id"] = f"{prefix}-{counter}"
        minted.append(out)
    return minted


def _object_text(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    parts: list[str] = []
    for key in keys:
        if key not in item:
            continue
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            text = "true" if value else "false"
        else:
            text = str(value).strip()
        if text:
            parts.append(f"{key}: {text}")
    return "; ".join(parts)


def _item_text(item: Any, field: str) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        keys = _LIST_ITEM_KEYS.get(field)
        if keys:
            return _object_text(item, keys)
        return _object_text(item, tuple(sorted(item.keys())))
    return str(item).strip()


def _slot_token(raw: str, *, max_len: int = 64) -> str:
    """Stable, filesystem-safe token for content identity inside a slot key."""
    text = str(raw).strip()
    if not text:
        return ""
    cleaned = re.sub(r"[^\w.\-]+", "_", text, flags=re.UNICODE)
    cleaned = cleaned.strip("_")
    if not cleaned:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        return f"h_{digest}"
    if len(cleaned) > max_len:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        return f"{cleaned[: max_len - 9]}_{digest}"
    return cleaned


def _list_item_slot(gate: str, field: str, item: Any) -> str:
    """Content-stable list slot (never array index — insert/reorder must keep ids)."""
    text = _item_text(item, field)
    if isinstance(item, dict):
        for key in ("name", "dependency", "id", "lens", "topic"):
            token = _slot_token(str(item.get(key, "")))
            if token:
                return f"{gate}.{field}[{key}={token}]"
        if field == "impact_surface":
            layer = _slot_token(str(item.get("layer", "")))
            area = _slot_token(str(item.get("area", "")))
            if layer or area:
                return f"{gate}.{field}[layer={layer}|area={area}]"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{gate}.{field}[sha256={digest}]"


def _unit(slot: str, text: str, *, unit_id: str = "") -> dict[str, Any] | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    out: dict[str, Any] = {"slot": slot, "text": cleaned}
    if unit_id.strip():
        out["id"] = unit_id.strip()
    return out


def _collect_gate_units(gate: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for field in _GATE_TEXT_FIELDS.get(gate, ()):
        unit = _unit(f"{gate}.{field}", str(payload.get(field, "")))
        if unit:
            units.append(unit)
    for field in _GATE_LIST_FIELDS.get(gate, ()):
        items = payload.get(field, [])
        if not isinstance(items, list):
            continue
        seen_slots: set[str] = set()
        for item in items:
            slot = _list_item_slot(gate, field, item)
            if slot in seen_slots:
                # Duplicate identity keys: disambiguate with content hash suffix.
                digest = hashlib.sha256(
                    _item_text(item, field).encode("utf-8")
                ).hexdigest()[:8]
                slot = f"{slot}#{digest}"
            seen_slots.add(slot)
            unit = _unit(slot, _item_text(item, field))
            if unit:
                units.append(unit)
    return units


def _collect_register_units(registers: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(registers, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}

    prior_units: list[dict[str, Any]] = []
    for entry in registers.get("prior") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", "")).strip()
        text = str(entry.get("text", ""))
        # Content-stable slot (never list index — reorder/insert must rematch).
        if entry_id:
            slot = f"user_prior:{entry_id}"
        else:
            digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]
            slot = f"user_prior:sha256={digest}"
        unit = _unit(slot, text, unit_id=entry_id)
        if unit:
            prior_units.append(unit)
    if prior_units:
        out["user_prior"] = prior_units

    assumption_units: list[dict[str, Any]] = []
    for entry in registers.get("assumptions") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", "")).strip()
        text = str(entry.get("text", ""))
        if entry_id:
            slot = f"assumptions:{entry_id}"
        else:
            digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]
            slot = f"assumptions:sha256={digest}"
        unit = _unit(slot, text, unit_id=entry_id)
        if unit:
            assumption_units.append(unit)
    if assumption_units:
        out["assumptions"] = assumption_units

    return out


def _previous_ids_by_slot(previous: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(previous, dict):
        return {}
    gates = previous.get("gates")
    if not isinstance(gates, dict):
        return {}
    mapping: dict[str, str] = {}
    for units in gates.values():
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            slot = str(unit.get("slot", "")).strip()
            unit_id = str(unit.get("id", "")).strip()
            if slot and unit_id:
                mapping[slot] = unit_id
    return mapping


def _apply_previous_ids(
    units: list[dict[str, Any]],
    previous_ids: dict[str, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for unit in units:
        item = dict(unit)
        if not str(item.get("id", "")).strip():
            slot = str(item.get("slot", "")).strip()
            if slot in previous_ids:
                item["id"] = previous_ids[slot]
        out.append(item)
    return out


def build_decision_fact(
    payloads: dict[str, dict[str, Any]],
    registers: dict[str, Any] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate gate payloads + registers into decision-fact.json payload."""
    if not isinstance(payloads, dict):
        raise ValueError("payloads must be an object")

    previous_ids = _previous_ids_by_slot(previous)
    gates: dict[str, list[dict[str, Any]]] = {}

    for gate in ("Q", "GL", "E", "D", "X", "R"):
        payload = payloads.get(gate)
        if not isinstance(payload, dict):
            continue
        units = _collect_gate_units(gate, payload)
        if not units:
            continue
        units = _apply_previous_ids(units, previous_ids)
        gates[gate] = _mint_ids(units, gate)

    for gate, units in _collect_register_units(registers).items():
        units = _apply_previous_ids(units, previous_ids)
        gates[gate] = _mint_ids(units, gate)

    return {"version": DECISION_FACT_VERSION, "gates": gates}


def validate_decision_fact(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["decision-fact must be an object"]
    if data.get("version") != DECISION_FACT_VERSION:
        errors.append(f"invalid version: {data.get('version')!r}")
    gates = data.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates must be an object")
        return errors

    seen_ids: set[str] = set()
    for gate, units in gates.items():
        gate_key = str(gate).strip()
        if not gate_key:
            errors.append("gates contains empty key")
            continue
        if not isinstance(units, list):
            errors.append(f"gates.{gate_key} must be an array")
            continue
        for index, unit in enumerate(units):
            if not isinstance(unit, dict):
                errors.append(f"gates.{gate_key}[{index}] must be an object")
                continue
            unit_id = str(unit.get("id", "")).strip()
            text = str(unit.get("text", "")).strip()
            if not unit_id:
                errors.append(f"gates.{gate_key}[{index}].id is required")
            elif unit_id in seen_ids:
                errors.append(f"duplicate unit id: {unit_id}")
            else:
                seen_ids.add(unit_id)
            if not text:
                errors.append(f"gates.{gate_key}[{index}].text is required")
    return errors


def load_decision_fact(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"decision-fact not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"decision-fact must be an object: {path}")
    errors = validate_decision_fact(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def save_decision_fact(path: Path, data: dict[str, Any]) -> None:
    errors = validate_decision_fact(data)
    if errors:
        raise ValueError("; ".join(errors))
    atomic_write_text(
        path,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    )


def _units_by_slot(fact: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Map slot → {gate, id, text} for every unit that carries a slot."""
    out: dict[str, dict[str, str]] = {}
    gates = fact.get("gates")
    if not isinstance(gates, dict):
        return out
    for gate, units in gates.items():
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            slot = str(unit.get("slot", "")).strip()
            if not slot:
                continue
            out[slot] = {
                "gate": str(gate),
                "id": str(unit.get("id", "")).strip(),
                "text": str(unit.get("text", "")).strip(),
            }
    return out


def audit_decision_fact_alignment(
    fact: dict[str, Any],
    payloads: dict[str, dict[str, Any]],
    registers: dict[str, Any] | None = None,
) -> list[str]:
    """Read-only audit: schema + payload/register slot/text alignment.

    Compares the file to a fresh cast from source (no previous). Slot set and
    texts must match. Id stability across re-export is enforced by
    ``export_decision_fact`` (slot rematch) and covered by its tests; this audit
    still verifies rematch keeps file ids for surviving slots.
    """
    errors = validate_decision_fact(fact)
    if errors:
        return errors

    gates = fact.get("gates")
    if isinstance(gates, dict):
        for gate, units in gates.items():
            if not isinstance(units, list):
                continue
            for index, unit in enumerate(units):
                if isinstance(unit, dict) and not str(unit.get("slot", "")).strip():
                    errors.append(f"gates.{gate}[{index}] missing slot (id rematch disabled)")
    if errors:
        return errors

    fresh = build_decision_fact(payloads, registers=registers, previous=None)
    actual = _units_by_slot(fact)
    expected = _units_by_slot(fresh)

    for slot in sorted(set(actual) - set(expected)):
        errors.append(f"orphan unit slot not in source: {slot} (id={actual[slot]['id']})")
    for slot in sorted(set(expected) - set(actual)):
        errors.append(f"missing unit for source slot: {slot}")
    for slot in sorted(set(actual) & set(expected)):
        a = actual[slot]
        e = expected[slot]
        if a["text"] != e["text"]:
            errors.append(f"text drift at slot {slot}: file diverges from source")
        if a["gate"] != e["gate"]:
            errors.append(
                f"gate drift at slot {slot}: file={a['gate']!r} expected={e['gate']!r}"
            )

    # Rematch invariant: rebuilding with this file as previous must keep ids.
    rematched = build_decision_fact(payloads, registers=registers, previous=fact)
    rematched_by_slot = _units_by_slot(rematched)
    for slot in sorted(set(actual) & set(rematched_by_slot)):
        if actual[slot]["id"] != rematched_by_slot[slot]["id"]:
            errors.append(
                f"id rematch failed at slot {slot}: "
                f"file={actual[slot]['id']!r} rematch={rematched_by_slot[slot]['id']!r}"
            )
    return errors


def build_export_decision_fact(
    payloads_dir: Path,
    out_path: Path,
    *,
    registers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build decision-fact payload in memory; preserve ids by stable slot.

    Invalid existing ``out_path`` raises (does not silently drop previous ids).
    """
    previous: dict[str, Any] | None = None
    if out_path.exists():
        previous = load_decision_fact(out_path)
    payloads = gate_payloads_for_session(payloads_dir)
    return build_decision_fact(payloads, registers=registers, previous=previous)


def export_decision_fact(
    payloads_dir: Path,
    out_path: Path,
    *,
    registers: dict[str, Any] | None = None,
) -> Path:
    """Build (or rebuild) decision-fact.json; preserve ids by slot; atomic write."""
    fact = build_export_decision_fact(
        payloads_dir,
        out_path,
        registers=registers,
    )
    save_decision_fact(out_path, fact)
    return out_path


def export_decision_fact_audited(
    payloads_dir: Path,
    out_path: Path,
    *,
    registers: dict[str, Any] | None = None,
) -> Path:
    """Build → audit → atomic save (no dirty file when audit fails)."""
    payloads = gate_payloads_for_session(payloads_dir)
    fact = build_export_decision_fact(
        payloads_dir,
        out_path,
        registers=registers,
    )
    alignment_errors = audit_decision_fact_alignment(
        fact,
        payloads,
        registers=registers,
    )
    if alignment_errors:
        raise ValueError(
            "decision-fact audit failed before write: "
            + "; ".join(alignment_errors)
        )
    save_decision_fact(out_path, fact)
    return out_path

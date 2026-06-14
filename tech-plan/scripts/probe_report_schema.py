#!/usr/bin/env python3
"""Schema and I/O for tech-plan round-{N}/{section}/probe-{seq}.json files (v3).

CLI:
    python3 probe_report_schema.py --schema
    python3 probe_report_schema.py --validate --path <probe-report.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from section_registry_schema import section_keys as _registry_section_keys
from gap_report_schema import (  # noqa: E402 — same package
    _DECISIONS,
    _KW_CRITERIA_KEYS,
    _STATUSES,
    find_item,
    kw0_pending_items,
    open_items,
    undecided_items,
    refiner_payload,
)

_GAP_KINDS_KW = frozenset({"kw", "kw0_pending"})
_GAP_KINDS_UPSTREAM = frozenset({"upstream_violation", "upstream_coverage"})
_GAP_KINDS_ALL = _GAP_KINDS_KW | _GAP_KINDS_UPSTREAM
_SCOPES_KW = frozenset({"subsection"})
_SCOPES_SECTION = frozenset({"section"})
_UPSTREAM_CRITERIA_KEYS = ("upstream_intent", "expected", "observed")

_SCHEMA: dict[str, Any] = {
    "version": "3",
    "kind": "probe",
    "item_fields": [
        "id",
        "gap_kind",
        "scope",
        "section_key",
        "section",
        "target_kw",
        "intent_gap",
        "kw_criteria",
        "upstream_section",
        "upstream_relation",
        "upstream_criteria",
        "sub_section_summary",
        "sub_section_text",
        "skip_key",
        "status",
        "decision",
    ],
    "enums": {
        "gap_kind": [
            "kw",
            "kw0_pending",
            "upstream_violation",
            "upstream_coverage",
        ],
        "scope": ["subsection", "section"],
        "status": list(_STATUSES),
        "decision": list(_DECISIONS),
    },
}


def get_schema() -> dict[str, Any]:
    """Return probe report schema dict."""
    from section_registry_schema import section_keys  # noqa: WPS433

    schema = dict(_SCHEMA)
    enums = dict(_SCHEMA["enums"])
    enums["section_key"] = list(section_keys())
    schema["enums"] = enums
    return schema


def _default_gap_kind(item: dict[str, Any]) -> str:
    status = str(item.get("status", "")).lower()
    if status == "kw0_pending":
        return "kw0_pending"
    return "kw"


def _is_upstream_gap(gap_kind: str) -> bool:
    return gap_kind in _GAP_KINDS_UPSTREAM


def upstream_open_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return open upstream gap items."""
    return [
        item
        for item in open_items(report)
        if _is_upstream_gap(str(item.get("gap_kind", "")).lower())
    ]


def kw_open_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return open KW gap items (excluding upstream)."""
    return [
        item
        for item in open_items(report)
        if str(item.get("gap_kind", "")).lower() == "kw"
    ]


def upstream_undecided_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return undecided upstream gap items."""
    return [
        item
        for item in undecided_items(report)
        if _is_upstream_gap(str(item.get("gap_kind", "")).lower())
    ]


def kw_undecided_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return undecided KW gap items (kw and kw0_pending)."""
    return [
        item
        for item in undecided_items(report)
        if str(item.get("gap_kind", "")).lower() in _GAP_KINDS_KW
    ]


def validate_probe_item(item: dict[str, Any], *, index: int = 0) -> list[str]:
    """Validate a single probe report item (v3 KW + upstream fields)."""
    errors: list[str] = []
    prefix = item.get("id") or f"items[{index}]"

    gap_kind = str(item.get("gap_kind") or _default_gap_kind(item)).lower()
    if gap_kind not in _GAP_KINDS_ALL:
        errors.append(f"{prefix}: invalid gap_kind: {gap_kind!r}")

    scope = str(item.get("scope") or ("section" if _is_upstream_gap(gap_kind) else "subsection")).lower()
    if _is_upstream_gap(gap_kind):
        if scope not in _SCOPES_SECTION:
            errors.append(f"{prefix}: upstream items require scope section")
    elif scope not in _SCOPES_KW:
        errors.append(f"{prefix}: invalid scope: {scope!r}")

    if gap_kind == "kw0_pending" and str(item.get("status", "")).lower() != "kw0_pending":
        errors.append(f"{prefix}: gap_kind kw0_pending requires status kw0_pending")

    for field in ("id", "section_key", "section", "sub_section_summary", "skip_key"):
        if not str(item.get(field, "")).strip():
            errors.append(f"{prefix}: missing required field: {field}")

    section_key = str(item.get("section_key", "")).upper()
    if section_key and section_key not in _registry_section_keys():
        errors.append(f"{prefix}: invalid section_key: {section_key!r}")

    status = str(item.get("status", "")).lower()
    if not status:
        errors.append(f"{prefix}: missing required field: status")
        return errors
    if status not in _STATUSES:
        errors.append(f"{prefix}: invalid status: {status!r}")
        return errors

    decision = item.get("decision", "—")
    if decision not in _DECISIONS:
        errors.append(f"{prefix}: invalid decision: {decision!r}")

    if item.get("sub_section_text") is None:
        errors.append(f"{prefix}: missing required field: sub_section_text")

    if _is_upstream_gap(gap_kind) and status in ("open", "resolved"):
        upstream_section = str(item.get("upstream_section", "")).upper()
        if upstream_section not in _registry_section_keys():
            errors.append(f"{prefix}: upstream_section required for upstream gaps")
        if item.get("target_kw") is not None:
            errors.append(f"{prefix}: upstream gaps must not include target_kw")
        if item.get("kw_criteria") is not None:
            errors.append(f"{prefix}: upstream gaps must not include kw_criteria")
        if item.get("intent_gap") is None:
            errors.append(f"{prefix}: intent_gap required when status is {status}")
        upstream_criteria = item.get("upstream_criteria")
        if status == "open":
            if upstream_criteria is None:
                errors.append(f"{prefix}: upstream_criteria required when status is open")
            elif not isinstance(upstream_criteria, dict):
                errors.append(f"{prefix}: upstream_criteria must be an object")
            else:
                for key in _UPSTREAM_CRITERIA_KEYS:
                    if not str(upstream_criteria.get(key, "")).strip():
                        errors.append(
                            f"{prefix}: upstream_criteria.{key} required when status is open"
                        )

    if status in ("open", "resolved") and gap_kind == "kw":
        raw_kw = item.get("target_kw")
        if raw_kw is None:
            errors.append(f"{prefix}: target_kw required when status is {status}")
        else:
            try:
                kw = int(raw_kw)
                if kw < 1 or kw > 4:
                    errors.append(f"{prefix}: target_kw must be 1–4, got {kw}")
            except (TypeError, ValueError):
                errors.append(f"{prefix}: invalid target_kw: {raw_kw!r}")

        if item.get("intent_gap") is None:
            errors.append(f"{prefix}: intent_gap required when status is {status}")

        kw_criteria = item.get("kw_criteria")
        if status == "open":
            if kw_criteria is None:
                errors.append(f"{prefix}: kw_criteria required when status is open")
            elif not isinstance(kw_criteria, dict):
                errors.append(f"{prefix}: kw_criteria must be an object")
            else:
                for key in _KW_CRITERIA_KEYS:
                    if not str(kw_criteria.get(key, "")).strip():
                        errors.append(
                            f"{prefix}: kw_criteria.{key} required when status is open"
                        )
        elif kw_criteria is not None and not isinstance(kw_criteria, dict):
            errors.append(f"{prefix}: kw_criteria must be an object")

    if status == "kw0_pending":
        if item.get("intent_gap") is None:
            errors.append(f"{prefix}: intent_gap required when status is kw0_pending")
        if item.get("kw_criteria") is not None:
            errors.append(f"{prefix}: kw0_pending items must not include kw_criteria")

    if status == "no_gap" and item.get("intent_gap"):
        errors.append(f"{prefix}: no_gap items must have empty intent_gap")

    return errors


def validate_probe_report(data: dict[str, Any]) -> list[str]:
    """Validate full probe report payload."""
    errors: list[str] = []

    if data.get("version") != "3":
        errors.append(f"invalid version: {data.get('version')!r} (expected '3')")
    if data.get("kind") != "probe":
        errors.append(f"invalid kind: {data.get('kind')!r} (expected 'probe')")

    try:
        if int(data.get("round", 0)) < 1:
            errors.append(f"invalid round: {data.get('round')!r}")
    except (TypeError, ValueError):
        errors.append(f"invalid round: {data.get('round')!r}")

    try:
        if int(data.get("probe_seq", 0)) < 1:
            errors.append(f"invalid probe_seq: {data.get('probe_seq')!r}")
    except (TypeError, ValueError):
        errors.append(f"invalid probe_seq: {data.get('probe_seq')!r}")

    section_key = str(data.get("section_key", "")).upper()
    if section_key not in _registry_section_keys():
        errors.append(f"invalid section_key: {section_key!r}")

    if not str(data.get("section", "")).strip():
        errors.append("missing required field: section")

    items = data.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list")
        return errors

    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"items[{index}] must be an object")
            continue
        errors.extend(validate_probe_item(item, index=index))
        item_id = str(item.get("id", "")).strip()
        if item_id:
            if item_id in seen_ids:
                errors.append(f"duplicate item id: {item_id}")
            seen_ids.add(item_id)
        item_section = str(item.get("section_key", "")).upper()
        if item_section and item_section != section_key:
            errors.append(
                f"{item_id or f'items[{index}]'}: section_key {item_section!r} "
                f"does not match report section {section_key!r}"
            )

    for field in ("anchor_failures", "anchor_candidates"):
        value = data.get(field, [])
        if value is None:
            continue
        if not isinstance(value, list):
            errors.append(f"{field} must be a list")

    return errors


def normalize_probe_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return item with normalized v3 fields."""
    gap_kind = str(item.get("gap_kind") or _default_gap_kind(item)).lower()
    default_scope = "section" if _is_upstream_gap(gap_kind) else "subsection"
    normalized: dict[str, Any] = {
        "id": str(item.get("id", "")),
        "gap_kind": gap_kind,
        "scope": str(item.get("scope") or default_scope).lower(),
        "section_key": str(item.get("section_key", "")).upper(),
        "section": str(item.get("section", "")),
        "sub_section_text": str(item.get("sub_section_text", "")),
        "sub_section_summary": str(item.get("sub_section_summary", "")),
        "skip_key": str(item.get("skip_key", "")),
        "intent_gap": str(item.get("intent_gap", "")),
        "kw_criteria": item.get("kw_criteria"),
        "status": str(item.get("status", "")).lower(),
    }
    decision = item.get("decision", "—")
    normalized["decision"] = decision if decision in _DECISIONS else "—"

    raw_kw = item.get("target_kw")
    normalized["target_kw"] = int(raw_kw) if raw_kw is not None else None

    upstream_section = item.get("upstream_section")
    normalized["upstream_section"] = (
        str(upstream_section).upper() if upstream_section else None
    )
    upstream_relation = item.get("upstream_relation")
    normalized["upstream_relation"] = str(upstream_relation) if upstream_relation else None
    normalized["upstream_criteria"] = item.get("upstream_criteria")
    return normalized


def normalize_probe_report(data: dict[str, Any]) -> dict[str, Any]:
    """Return validated-normalized probe report payload."""
    return {
        "version": "3",
        "kind": "probe",
        "round": int(data["round"]),
        "revision": int(data.get("revision", 1)),
        "cycle_id": str(data.get("cycle_id", "")),
        "section_key": str(data["section_key"]).upper(),
        "section": str(data["section"]),
        "probe_seq": int(data["probe_seq"]),
        "anchor_failures": list(data.get("anchor_failures") or []),
        "anchor_candidates": list(data.get("anchor_candidates") or []),
        "items": [normalize_probe_item(item) for item in data.get("items") or []],
    }


def load_probe_report(path: Path) -> dict[str, Any]:
    """Load and normalize probe report from disk."""
    if not path.exists():
        raise FileNotFoundError(f"probe report not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_probe_report(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_probe_report(data)


def save_probe_report(path: Path, data: dict[str, Any]) -> None:
    """Validate and write probe report JSON."""
    errors = validate_probe_report(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_probe_report(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _update_probe_item_field(
    report: dict[str, Any],
    *,
    item_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(report)
    items: list[dict[str, Any]] = []
    found = False
    for item in report.get("items", []):
        if item.get("id") == item_id:
            found = True
            row = dict(item)
            row.update(updates)
            items.append(row)
        else:
            items.append(dict(item))
    if not found:
        raise ValueError(f"gap item not found: {item_id!r}")
    updated["items"] = items
    return normalize_probe_report(updated)


def update_probe_item_decision(
    report: dict[str, Any],
    *,
    item_id: str,
    decision: str,
) -> dict[str, Any]:
    """Return updated probe report with item decision set."""
    if decision not in {"accept", "skip", "redirect"}:
        raise ValueError(f"decision must be accept, skip, or redirect, got {decision!r}")
    return _update_probe_item_field(report, item_id=item_id, updates={"decision": decision})


def update_probe_item_status(
    report: dict[str, Any],
    *,
    item_id: str,
    status: str,
) -> dict[str, Any]:
    """Return updated probe report with item status set."""
    if status not in _STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    return _update_probe_item_field(report, item_id=item_id, updates={"status": status})


def refiner_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Return refiner-runner dispatch fields from a probe gap item."""
    gap_kind = str(item.get("gap_kind", "kw")).lower()
    payload: dict[str, Any] = {
        "gap_item_id": item["id"],
        "section": item["section"],
        "section_key": item["section_key"],
        "scope": item.get("scope"),
        "gap_kind": gap_kind,
        "sub_section_text": item["sub_section_text"],
        "intent_gap": item["intent_gap"],
    }
    if _is_upstream_gap(gap_kind):
        payload.update(
            {
                "upstream_section": item.get("upstream_section"),
                "upstream_relation": item.get("upstream_relation"),
                "upstream_criteria": item.get("upstream_criteria"),
                "target_kw": None,
                "kw_criteria": None,
            }
        )
        return payload
    payload.update(
        {
            "target_kw": item.get("target_kw"),
            "kw_criteria": item.get("kw_criteria"),
            "upstream_section": None,
            "upstream_relation": None,
            "upstream_criteria": None,
        }
    )
    return payload


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan probe report schema")
    parser.add_argument("--schema", action="store_true", help="Print schema JSON")
    parser.add_argument("--validate", action="store_true", help="Validate probe report")
    parser.add_argument("--read", action="store_true", help="Read probe report as JSON")
    parser.add_argument("--path", type=Path, help="Path to probe-NNN.json")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), ensure_ascii=False, indent=2))
        return 0

    if not args.path:
        print("--validate/--read requires --path", file=sys.stderr)
        return 1

    path = args.path.resolve()
    if args.validate:
        try:
            load_probe_report(path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "path": str(path)}))
        return 0

    if args.read:
        try:
            payload = load_probe_report(path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())

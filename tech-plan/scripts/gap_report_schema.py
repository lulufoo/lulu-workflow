#!/usr/bin/env python3
"""Schema and I/O for tech-plan gap-report-round-{N}.json files.

CLI:
    python3 gap_report_schema.py --schema
    python3 gap_report_schema.py --validate --path <gap-report.json>
    python3 gap_report_schema.py --read --path <gap-report.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from section_registry_schema import section_keys as _load_section_keys

_SCHEMA: dict[str, Any] = {
    "version": "2",
    "item_fields": [
        "id",
        "section_key",
        "section",
        "target_kw",
        "intent_gap",
        "kw_criteria",
        "sub_section_summary",
        "sub_section_text",
        "skip_key",
        "status",
        "decision",
    ],
    "enums": {
        "status": ["open", "no_gap", "resolved", "kw0_pending"],
        "decision": ["—", "accept", "skip", "redirect"],
    },
}

_STATUSES = frozenset(_SCHEMA["enums"]["status"])
_DECISIONS = frozenset(_SCHEMA["enums"]["decision"])
_KW_CRITERIA_KEYS = ("kw0", "kw1", "kw2", "kw3", "kw4")


def get_schema() -> dict[str, Any]:
    """Return gap report schema dict."""
    schema = dict(_SCHEMA)
    enums = dict(_SCHEMA["enums"])
    enums["section_key"] = list(_load_section_keys())
    schema["enums"] = enums
    return schema


def gap_report_path(revision_dir: Path, round_n: int) -> Path:
    """Return canonical gap report JSON path for a round."""
    return revision_dir / f"gap-report-round-{round_n}.json"


def validate_item(item: dict[str, Any], *, index: int = 0) -> list[str]:
    """Validate a single gap report item."""
    errors: list[str] = []
    prefix = item.get("id") or f"items[{index}]"

    for field in ("id", "section_key", "section", "sub_section_summary", "skip_key"):
        if not str(item.get(field, "")).strip():
            errors.append(f"{prefix}: missing required field: {field}")

    section_key = str(item.get("section_key", "")).upper()
    if section_key and section_key not in _load_section_keys():
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

    if status in ("open", "resolved"):
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


def validate_gap_report(data: dict[str, Any]) -> list[str]:
    """Validate full gap report payload."""
    errors: list[str] = []

    if data.get("version") != "2":
        errors.append(f"invalid version: {data.get('version')!r} (expected '2')")

    round_raw = data.get("round")
    try:
        if int(round_raw) < 1:
            errors.append(f"invalid round: {round_raw!r}")
    except (TypeError, ValueError):
        errors.append(f"invalid round: {round_raw!r}")

    items = data.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list")
        return errors

    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"items[{index}] must be an object")
            continue
        errors.extend(validate_item(item, index=index))
        item_id = str(item.get("id", "")).strip()
        if item_id:
            if item_id in seen_ids:
                errors.append(f"duplicate item id: {item_id}")
            seen_ids.add(item_id)

    for field in ("anchor_failures", "anchor_candidates"):
        value = data.get(field, [])
        if value is None:
            continue
        if not isinstance(value, list):
            errors.append(f"{field} must be a list")

    return errors


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return item with normalized enums and types."""
    normalized = dict(item)
    normalized["section_key"] = str(item.get("section_key", "")).upper()
    normalized["status"] = str(item.get("status", "")).lower()
    decision = item.get("decision", "—")
    normalized["decision"] = decision if decision in _DECISIONS else "—"
    normalized["sub_section_text"] = str(item.get("sub_section_text", ""))
    normalized["sub_section_summary"] = str(item.get("sub_section_summary", ""))
    normalized["skip_key"] = str(item.get("skip_key", ""))
    normalized["intent_gap"] = str(item.get("intent_gap", ""))

    raw_kw = item.get("target_kw")
    normalized["target_kw"] = int(raw_kw) if raw_kw is not None else None

    normalized["kw_criteria"] = item.get("kw_criteria")

    return normalized


def normalize_gap_report(data: dict[str, Any]) -> dict[str, Any]:
    """Return validated-normalized gap report payload."""
    return {
        "version": "2",
        "round": int(data["round"]),
        "revision": int(data.get("revision", 1)),
        "cycle_id": str(data.get("cycle_id", "")),
        "anchor_failures": list(data.get("anchor_failures") or []),
        "anchor_candidates": list(data.get("anchor_candidates") or []),
        "items": [normalize_item(item) for item in data.get("items") or []],
    }


def load_gap_report(path: Path) -> dict[str, Any]:
    """Load and normalize gap report from disk."""
    if not path.exists():
        raise FileNotFoundError(f"gap report not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_gap_report(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_gap_report(data)


def save_gap_report(path: Path, data: dict[str, Any]) -> None:
    """Validate and write gap report JSON."""
    errors = validate_gap_report(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_gap_report(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def find_item(report: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    """Return item by id or None."""
    target = item_id.strip()
    for item in report.get("items", []):
        if item.get("id") == target:
            return item
    return None


def open_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return items with status open."""
    return [item for item in report.get("items", []) if item.get("status") == "open"]


def undecided_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return open items awaiting a human decision (decision still —)."""
    return [
        item
        for item in report.get("items", [])
        if item.get("status") == "open" and item.get("decision", "—") == "—"
    ]


def kw0_pending_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return items waiting for user to supply initial sub-section content."""
    return [item for item in report.get("items", []) if item.get("status") == "kw0_pending"]


def update_item_decision(
    report: dict[str, Any],
    *,
    item_id: str,
    decision: str,
) -> dict[str, Any]:
    """Return updated report with item decision set."""
    if decision not in {"accept", "skip", "redirect"}:
        raise ValueError(f"decision must be accept, skip, or redirect, got {decision!r}")

    updated = dict(report)
    items: list[dict[str, Any]] = []
    found = False
    for item in report.get("items", []):
        if item.get("id") == item_id:
            found = True
            row = dict(item)
            row["decision"] = decision
            items.append(row)
        else:
            items.append(dict(item))
    if not found:
        raise ValueError(f"gap item not found: {item_id!r}")
    updated["items"] = items
    return normalize_gap_report(updated)


def update_item_status(
    report: dict[str, Any],
    *,
    item_id: str,
    status: str,
) -> dict[str, Any]:
    """Return updated report with item status set."""
    if status not in _STATUSES:
        raise ValueError(f"invalid status: {status!r}")

    updated = dict(report)
    items: list[dict[str, Any]] = []
    found = False
    for item in report.get("items", []):
        if item.get("id") == item_id:
            found = True
            row = dict(item)
            row["status"] = status
            items.append(row)
        else:
            items.append(dict(item))
    if not found:
        raise ValueError(f"gap item not found: {item_id!r}")
    updated["items"] = items
    return normalize_gap_report(updated)


def refiner_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Return refiner-runner dispatch fields from a gap item."""
    return {
        "gap_item_id": item["id"],
        "section": item["section"],
        "section_key": item["section_key"],
        "sub_section_text": item["sub_section_text"],
        "target_kw": item["target_kw"],
        "intent_gap": item["intent_gap"],
        "kw_criteria": item.get("kw_criteria"),
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan gap report schema")
    parser.add_argument("--schema", action="store_true", help="Print schema JSON")
    parser.add_argument("--validate", action="store_true", help="Validate gap report")
    parser.add_argument("--read", action="store_true", help="Read gap report as JSON")
    parser.add_argument("--path", type=Path, help="Path to gap-report-round-N.json")
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
            load_gap_report(path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "path": str(path)}))
        return 0

    if args.read:
        try:
            payload = load_gap_report(path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())

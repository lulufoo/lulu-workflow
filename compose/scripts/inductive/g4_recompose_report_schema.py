#!/usr/bin/env python3
"""Schema and I/O for g4-recompose-report.json (Gate 4 semantic audit verdict).

Single report per inductive session. Written by g4-recompose-runner subagent;
read by parent via inductive_g4_control.py list/check subcommands. Holds only
the four **semantic** predicates (conflicts / buildable / reversible /
verifiable) — the two **structural** predicates (reforms_shape /
shape_absorbed) stay script-checkable in inductive_g3_section_control.py
recompose-check and are merged with this report only at gate-close G4.

Thinness limits (adjust here):
  MAX_FACTS          max audit facts
  MAX_FACT_CHARS     max chars per fact
  MAX_CONFLICTS      max conflicts per report
  MAX_CODE_REFS      max code_refs per conflict
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_FACTS = 8
MAX_FACT_CHARS = 200
MAX_CONFLICTS = 10
MAX_CODE_REFS = 6

PRODUCED_BY = frozenset({"subagent"})

_REQUIRED_FIELDS = (
    "version",
    "conflicts",
    "buildable",
    "reversible",
    "verifiable",
    "facts",
    "produced_by",
    "created_at",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def g4_report_path(out_dir: Path) -> Path:
    return out_dir / "g4-recompose-report.json"


def init_report() -> dict[str, Any]:
    return {
        "version": "1",
        "conflicts": [],
        "buildable": True,
        "reversible": True,
        "verifiable": True,
        "facts": [],
        "produced_by": "subagent",
        "created_at": _now_iso(),
    }


def validate_conflict(conflict: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"conflicts[{index}]"
    if not isinstance(conflict, dict):
        return [f"{prefix}: must be an object"]

    description = str(conflict.get("description", "")).strip()
    if not description:
        errors.append(f"{prefix}: description is required")

    sections = conflict.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append(f"{prefix}: sections must be a non-empty list")
        sections = []

    owning_section = conflict.get("owning_section")
    if owning_section is not None:
        if not isinstance(owning_section, str) or not owning_section.strip():
            errors.append(f"{prefix}: owning_section must be a non-empty string when set")
        elif sections and owning_section not in sections:
            errors.append(f"{prefix}: owning_section {owning_section!r} not in sections")

    code_refs = conflict.get("code_refs")
    if code_refs is not None:
        if not isinstance(code_refs, list):
            errors.append(f"{prefix}: code_refs must be a list")
        elif len(code_refs) > MAX_CODE_REFS:
            errors.append(f"{prefix}: code_refs exceeds max {MAX_CODE_REFS}")

    return errors


def validate_report(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field {field!r}")

    produced = str(data.get("produced_by", "")).lower()
    if produced not in PRODUCED_BY:
        errors.append(f"invalid produced_by: {data.get('produced_by')!r}")

    for field in ("buildable", "reversible", "verifiable"):
        if not isinstance(data.get(field), bool):
            errors.append(f"{field!r} must be a bool")

    conflicts = data.get("conflicts")
    if not isinstance(conflicts, list):
        errors.append("conflicts must be a list")
    elif len(conflicts) > MAX_CONFLICTS:
        errors.append(f"conflicts exceeds max {MAX_CONFLICTS}")
    elif isinstance(conflicts, list):
        for i, conflict in enumerate(conflicts):
            errors.extend(validate_conflict(conflict, i))

    facts = data.get("facts")
    if not isinstance(facts, list):
        errors.append("facts must be a list")
    elif len(facts) > MAX_FACTS:
        errors.append(f"facts exceeds max {MAX_FACTS}")
    elif isinstance(facts, list):
        for i, fact in enumerate(facts):
            if not isinstance(fact, str):
                errors.append(f"facts[{i}] must be a string")
            elif len(fact) > MAX_FACT_CHARS:
                errors.append(f"facts[{i}] exceeds {MAX_FACT_CHARS} chars")

    # A "clean" verdict (no conflicts, everything true) still needs an audit
    # trail — ok/clean reports must include at least one distilled fact.
    is_clean = (
        isinstance(conflicts, list)
        and not conflicts
        and data.get("buildable") is True
        and data.get("reversible") is True
        and data.get("verifiable") is True
    )
    if is_clean and isinstance(facts, list) and not any(str(f).strip() for f in facts):
        errors.append("a clean verdict (no conflicts, all true) requires non-empty facts")

    return errors


def normalize_report(raw: dict[str, Any]) -> dict[str, Any]:
    conflicts_raw = raw.get("conflicts") or []
    conflicts: list[dict[str, Any]] = []
    if isinstance(conflicts_raw, list):
        for item in conflicts_raw:
            if isinstance(item, dict):
                conflicts.append(
                    {
                        "description": str(item.get("description", "")),
                        "sections": list(item.get("sections") or []),
                        "owning_section": item.get("owning_section"),
                        "code_refs": list(item.get("code_refs") or []),
                    }
                )

    return {
        "version": "1",
        "conflicts": conflicts,
        "buildable": bool(raw.get("buildable", False)),
        "reversible": bool(raw.get("reversible", False)),
        "verifiable": bool(raw.get("verifiable", False)),
        "facts": [str(f) for f in (raw.get("facts") or [])],
        "produced_by": str(raw.get("produced_by", "subagent")).lower(),
        "created_at": raw.get("created_at") or _now_iso(),
    }


def load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"g4 recompose report not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_report(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def save_report(path: Path, data: dict[str, Any]) -> None:
    normalized = normalize_report(data)
    errors = validate_report(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def delete_report(out_dir: Path) -> bool:
    path = g4_report_path(out_dir)
    if path.exists():
        path.unlink()
        return True
    return False


def check_report_readable(report: dict[str, Any]) -> dict[str, Any]:
    """Schema check for parent list/check; unresolved conflicts are valid but not closable."""
    errors = validate_report(report)
    closable = (
        not errors
        and not report.get("conflicts")
        and bool(report.get("buildable"))
        and bool(report.get("reversible"))
        and bool(report.get("verifiable"))
    )
    return {
        "ok": closable,
        "schema_ok": len(errors) == 0,
        "errors": errors,
        "closable": closable,
        "conflicts": report.get("conflicts", []),
        "buildable": report.get("buildable"),
        "reversible": report.get("reversible"),
        "verifiable": report.get("verifiable"),
    }

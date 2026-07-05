#!/usr/bin/env python3
"""Schema and I/O for g2-topology-report.json (Gate 2 topology verdict).

Single report per inductive session. Written by g2-grounding-runner subagent;
read by parent via inductive_g2_control.py list/check subcommands.

Thinness limits (adjust here):
  MAX_G2_FACTS           max topology facts
  MAX_G2_FACT_CHARS      max chars per fact
  MAX_G2_DIVERGENCES     max divergences when shape_breaking
  MAX_G2_CODE_REFS       max code_refs per divergence
  MAX_CHECKLIST_ITEMS    max checklist rows
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_G2_FACTS = 5
MAX_G2_FACT_CHARS = 120
MAX_G2_DIVERGENCES = 3
MAX_G2_CODE_REFS = 6
MAX_CHECKLIST_ITEMS = 12

VERDICTS = frozenset({"ok", "shape_breaking"})
CHECKLIST_RESULTS = frozenset({"confirmed", "not_applicable", "contradiction"})
PRODUCED_BY = frozenset({"subagent"})

_LINE_DETAIL_IN_FACT = re.compile(
    r"\(\s*L?\d+\s*-\s*L?\d+\s*\)|\(\s*L?\d+\s*-\s*\d+\s*\)|::\w+\s*\(\s*\d+",
    re.IGNORECASE,
)

_REQUIRED_FIELDS = (
    "version",
    "verdict",
    "facts",
    "divergences",
    "produced_by",
    "created_at",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def g2_report_path(out_dir: Path) -> Path:
    return out_dir / "g2-topology-report.json"


def init_report() -> dict[str, Any]:
    return {
        "version": "1",
        "verdict": "ok",
        "facts": [],
        "divergences": [],
        "checklist": [],
        "produced_by": "subagent",
        "created_at": _now_iso(),
    }


def validate_checklist_item(item: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"checklist[{index}]"
    if not isinstance(item, dict):
        return [f"{prefix}: must be an object"]
    result = str(item.get("result", "")).lower()
    if result not in CHECKLIST_RESULTS:
        errors.append(f"{prefix}: invalid result {result!r}")
    claim = str(item.get("claim", "")).strip()
    if not claim:
        errors.append(f"{prefix}: claim is required")
    return errors


def validate_divergence(div: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"divergences[{index}]"
    if not isinstance(div, dict):
        return [f"{prefix}: must be an object"]
    shape_claim = str(div.get("shape_claim", "")).strip()
    finding = str(div.get("finding", "")).strip()
    if not shape_claim:
        errors.append(f"{prefix}: shape_claim is required")
    if not finding:
        errors.append(f"{prefix}: finding is required")
    code_refs = div.get("code_refs")
    if code_refs is not None:
        if not isinstance(code_refs, list):
            errors.append(f"{prefix}: code_refs must be a list")
        elif len(code_refs) > MAX_G2_CODE_REFS:
            errors.append(f"{prefix}: code_refs exceeds max {MAX_G2_CODE_REFS}")
    return errors


def validate_report(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    verdict = str(data.get("verdict", "")).lower()
    if verdict not in VERDICTS:
        errors.append(f"invalid verdict: {data.get('verdict')!r}")

    produced = str(data.get("produced_by", "")).lower()
    if produced not in PRODUCED_BY:
        errors.append(f"invalid produced_by: {data.get('produced_by')!r}")

    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field {field!r}")

    facts = data.get("facts")
    if not isinstance(facts, list):
        errors.append("facts must be a list")
    elif len(facts) > MAX_G2_FACTS:
        errors.append(f"facts exceeds max {MAX_G2_FACTS}")
    elif isinstance(facts, list):
        for i, fact in enumerate(facts):
            if not isinstance(fact, str):
                errors.append(f"facts[{i}] must be a string")
            elif len(fact) > MAX_G2_FACT_CHARS:
                errors.append(f"facts[{i}] exceeds {MAX_G2_FACT_CHARS} chars")
            elif _LINE_DETAIL_IN_FACT.search(fact):
                errors.append(
                    f"facts[{i}] must stay topology-level; no line-level detail"
                )

    divergences = data.get("divergences")
    if not isinstance(divergences, list):
        errors.append("divergences must be a list")
    elif len(divergences) > MAX_G2_DIVERGENCES:
        errors.append(f"divergences exceeds max {MAX_G2_DIVERGENCES}")
    elif isinstance(divergences, list):
        for i, div in enumerate(divergences):
            errors.extend(validate_divergence(div, i))

    checklist = data.get("checklist", [])
    if checklist is not None and not isinstance(checklist, list):
        errors.append("checklist must be a list")
    elif isinstance(checklist, list):
        if len(checklist) > MAX_CHECKLIST_ITEMS:
            errors.append(f"checklist exceeds max {MAX_CHECKLIST_ITEMS}")
        for i, item in enumerate(checklist):
            errors.extend(validate_checklist_item(item, i))

    if verdict == "ok" and isinstance(facts, list):
        if not any(str(f).strip() for f in facts):
            errors.append("verdict ok requires non-empty facts")

    if verdict == "shape_breaking" and isinstance(divergences, list):
        if not divergences:
            errors.append("verdict shape_breaking requires at least one divergence")

    return errors


def normalize_report(raw: dict[str, Any]) -> dict[str, Any]:
    checklist_raw = raw.get("checklist") or []
    checklist: list[dict[str, Any]] = []
    if isinstance(checklist_raw, list):
        for item in checklist_raw:
            if isinstance(item, dict):
                checklist.append(
                    {
                        "constraint_id": str(item.get("constraint_id", "")),
                        "claim": str(item.get("claim", "")),
                        "result": str(item.get("result", "")).lower(),
                    }
                )

    divergences_raw = raw.get("divergences") or []
    divergences: list[dict[str, Any]] = []
    if isinstance(divergences_raw, list):
        for item in divergences_raw:
            if isinstance(item, dict):
                divergences.append(
                    {
                        "constraint_id": str(item.get("constraint_id", "")),
                        "shape_claim": str(item.get("shape_claim", "")),
                        "finding": str(item.get("finding", "")),
                        "code_refs": list(item.get("code_refs") or []),
                    }
                )

    return {
        "version": "1",
        "verdict": str(raw.get("verdict", "")).lower(),
        "facts": [str(f) for f in (raw.get("facts") or [])],
        "divergences": divergences,
        "checklist": checklist,
        "produced_by": str(raw.get("produced_by", "subagent")).lower(),
        "created_at": raw.get("created_at") or _now_iso(),
    }


def load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"g2 topology report not found: {path}")
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
    path = g2_report_path(out_dir)
    if path.exists():
        path.unlink()
        return True
    return False


def check_report_for_gate_close(report: dict[str, Any]) -> dict[str, Any]:
    errors = validate_report(report)
    if errors:
        return {"ok": False, "verdict": report.get("verdict"), "errors": errors}
    verdict = str(report.get("verdict", "")).lower()
    if verdict != "ok":
        return {
            "ok": False,
            "verdict": verdict,
            "errors": [f"verdict is {verdict!r}; gate-close G2 requires ok"],
        }
    return {"ok": True, "verdict": verdict, "errors": []}


def check_report_readable(report: dict[str, Any]) -> dict[str, Any]:
    """Schema check for parent list/check; shape_breaking is valid but not closable."""
    errors = validate_report(report)
    verdict = str(report.get("verdict", "")).lower()
    closable = verdict == "ok" and not errors
    return {
        "ok": closable,
        "schema_ok": len(errors) == 0,
        "verdict": verdict,
        "errors": errors,
        "closable": closable,
    }

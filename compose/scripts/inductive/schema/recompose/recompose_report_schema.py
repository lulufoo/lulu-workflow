#!/usr/bin/env python3
"""Schema and I/O for g4-recompose-report.json (Gate 4 internal audit).

One report per working slice. Binds facts/opens digests; does not copy facts.
Empty findings are valid only when buildable, reversible, and verifiable
are all true.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parents[3] / "_kernel"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from compose_state_lock import durable_write_json  # noqa: E402

REPORT_BASENAME = "g4-recompose-report.json"
REPORT_VERSION = 1
PRODUCED_BY = frozenset({"subagent"})
_REQUIRED_FIELDS = (
    "version",
    "facts_digest",
    "opens_digest",
    "findings",
    "buildable",
    "reversible",
    "verifiable",
    "evidence",
    "produced_by",
    "created_at",
)
_ALLOWED_FIELDS = frozenset(_REQUIRED_FIELDS)
_FORBIDDEN_FIELDS = frozenset(
    {
        "conflicts",
        "reforms_shape",
        "shape_absorbed",
        "facts",
        "sections",
        "owning_section",
    }
)
_FINDING_REQUIRED = ("question", "basis", "blocking", "lens")
_FINDING_ALLOWED = frozenset(_FINDING_REQUIRED)
_FINDING_FORBIDDEN = frozenset({"sections", "owning_section", "conflicts"})
_EVIDENCE_KEYS = ("buildable", "reversible", "verifiable")
_MAX_EVIDENCE_CHARS = 200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def recompose_report_path(out_dir: Path) -> Path:
    return Path(out_dir) / REPORT_BASENAME


def _validate_finding(finding: Any, index: int) -> list[str]:
    prefix = f"findings[{index}]"
    if not isinstance(finding, dict):
        return [f"{prefix}: must be an object"]
    errors: list[str] = []
    forbidden = set(finding) & _FINDING_FORBIDDEN
    if forbidden:
        errors.append(f"{prefix}: forbidden fields {sorted(forbidden)}")
    extra = set(finding) - _FINDING_ALLOWED - _FINDING_FORBIDDEN
    if extra:
        errors.append(f"{prefix}: unexpected fields {sorted(extra)}")
    question = finding.get("question")
    if not isinstance(question, str) or not question.strip():
        errors.append(f"{prefix}: question is required")
    basis = finding.get("basis")
    if not isinstance(basis, str) or not basis.strip():
        errors.append(f"{prefix}: basis is required")
    if not isinstance(finding.get("blocking"), bool):
        errors.append(f"{prefix}: blocking must be a bool")
    lens = finding.get("lens")
    if not isinstance(lens, str) or not lens.strip():
        errors.append(f"{prefix}: lens is required")
    return errors


def validate_report(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["report must be an object"]
    forbidden = set(data) & _FORBIDDEN_FIELDS
    if forbidden:
        errors.append(f"forbidden fields {sorted(forbidden)}")
    extra = set(data) - _ALLOWED_FIELDS - _FORBIDDEN_FIELDS
    if extra:
        errors.append(f"unexpected fields {sorted(extra)}")
    if data.get("version") != REPORT_VERSION:
        errors.append(f"invalid version: {data.get('version')!r}")
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field {field!r}")
    for field in ("facts_digest", "opens_digest"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")
    produced = str(data.get("produced_by", "")).lower()
    if produced not in PRODUCED_BY:
        errors.append(f"invalid produced_by: {data.get('produced_by')!r}")
    for field in ("buildable", "reversible", "verifiable"):
        if not isinstance(data.get(field), bool):
            errors.append(f"{field!r} must be a bool")
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("evidence must be an object")
    else:
        for key in _EVIDENCE_KEYS:
            value = evidence.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"evidence.{key} must be a non-empty string")
            elif len(value) > _MAX_EVIDENCE_CHARS:
                errors.append(f"evidence.{key} exceeds {_MAX_EVIDENCE_CHARS} chars")
    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        findings = []
    else:
        for index, finding in enumerate(findings):
            errors.extend(_validate_finding(finding, index))
    predicates_true = (
        data.get("buildable") is True
        and data.get("reversible") is True
        and data.get("verifiable") is True
    )
    if isinstance(findings, list) and not findings and not predicates_true:
        errors.append("empty findings are valid only when all three predicates are true")
    return errors


def normalize_report(raw: dict[str, Any]) -> dict[str, Any]:
    findings_raw = raw.get("findings") or []
    findings: list[dict[str, Any]] = []
    if isinstance(findings_raw, list):
        for item in findings_raw:
            if not isinstance(item, dict):
                continue
            findings.append(
                {
                    "question": str(item.get("question", "")).strip(),
                    "basis": str(item.get("basis", "")).strip(),
                    "blocking": bool(item.get("blocking", False)),
                    "lens": str(item.get("lens", "")).strip().upper(),
                }
            )
    evidence_raw = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    evidence = {
        key: str(evidence_raw.get(key, "")).strip() for key in _EVIDENCE_KEYS
    }
    return {
        "version": REPORT_VERSION,
        "facts_digest": str(raw.get("facts_digest", "")).strip(),
        "opens_digest": str(raw.get("opens_digest", "")).strip(),
        "findings": findings,
        "buildable": bool(raw.get("buildable", False)),
        "reversible": bool(raw.get("reversible", False)),
        "verifiable": bool(raw.get("verifiable", False)),
        "evidence": evidence,
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


def save_report(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_report(data)
    errors = validate_report(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(path, normalized)
    return normalized


def delete_report(out_dir: Path) -> bool:
    path = recompose_report_path(out_dir)
    if path.exists():
        path.unlink()
        return True
    return False


def allowed_finding_lenses(facts: Any, opens: Any) -> set[str]:
    """Lenses stamped on current Opens or a fact's lens."""
    allowed: set[str] = set()
    if isinstance(opens, list):
        for item in opens:
            if not isinstance(item, dict):
                continue
            lens = str(item.get("lens") or "").strip().upper()
            if lens:
                allowed.add(lens)
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            lens = str(fact.get("lens") or "").strip().upper()
            if lens:
                allowed.add(lens)
    return allowed


def validate_finding_lens_sources(
    findings: Any, facts: Any, opens: Any
) -> list[str]:
    """Fail findings whose lens is not on an Open or a fact."""
    if not isinstance(findings, list):
        return []
    allowed = allowed_finding_lenses(facts, opens)
    errors: list[str] = []
    for index, item in enumerate(findings):
        if not isinstance(item, dict):
            continue
        lens = str(item.get("lens") or "").strip().upper()
        if not lens:
            continue
        if lens not in allowed:
            errors.append(
                f"findings[{index}].lens has no Open.lens or fact lens source"
            )
    return errors


def check_report_readable(report: dict[str, Any]) -> dict[str, Any]:
    errors = validate_report(report)
    closable = (
        not errors
        and not report.get("findings")
        and report.get("buildable") is True
        and report.get("reversible") is True
        and report.get("verifiable") is True
    )
    return {
        "ok": closable,
        "schema_ok": len(errors) == 0,
        "errors": errors,
        "closable": closable,
        "findings": report.get("findings", []),
        "buildable": report.get("buildable"),
        "reversible": report.get("reversible"),
        "verifiable": report.get("verifiable"),
        "facts_digest": report.get("facts_digest"),
        "opens_digest": report.get("opens_digest"),
    }

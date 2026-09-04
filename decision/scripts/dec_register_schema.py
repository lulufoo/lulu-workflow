#!/usr/bin/env python3
"""Schema and I/O for decision registers.json.

Design rationale: docs/domain/archive/decision/decision-risk-release-timing-design.md
Evidence gate (check_result / check_evidence):
    docs/domain/archive/decision/decision-risk-release-evidence-gate-design.md
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dec_io import atomic_write_text

PRIOR_KINDS = frozenset({"judgment", "preference", "concern", "excluded"})
REGISTER_STATES = frozenset({"pending", "verified", "invalidated"})
# Active spine sources: O–R (+ DC is not a register source).
# RR / V remain only for historical entry.source values on loaded sessions;
# they are not GATE_ORDER gates after risk_state redesign.
REGISTER_SOURCES = frozenset({"O", "Q", "GL", "E", "D", "X", "R", "RR", "V"})
RISK_LEVELS = frozenset({"H", "M", "L", "none"})
RISK_CLASSES = frozenset({"decision", "implementation", "pending", "none"})
RISK_STATES = frozenset({"open", "ignore", "completed", "none"})
RISK_SOURCE_KINDS = frozenset({"prior", "assumption", "constraint"})
CHECK_RESULTS = frozenset({"pass", "fail"})
# Levels allowed to release with literal `Accepted` (no check evidence).
ACCEPTED_RISK_LEVELS = frozenset({"M", "L"})
_RISK_FIELD_KEYS = (
    "risk_level",
    "risk_class",
    "risk_state",
    "risk_consequence",
    "release_terms",
    "check_result",
    "check_evidence",
)
# Fields cleared together when a completed row reopens.
RELEASE_RECORD_KEYS = ("release_terms", "check_result", "check_evidence")


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
            "constraints": [],
            "risks": [],
            "next_prior_seq": 1,
            "next_assumption_seq": 1,
            "next_constraint_seq": 1,
            "next_risk_seq": 1,
            "updated_at": _now_iso(),
        }
    )


RELEASE_TERMS_PARTS = ("Method:", "Owner:", "Timing:", "Release condition:")


def validate_release_terms(terms: str, *, entry_id: str) -> None:
    text = str(terms).strip()
    if not text:
        raise ValueError(f"{entry_id}: release_terms is required")
    if text.startswith("Handoff:"):
        raise ValueError(f"{entry_id}: Handoff: forbidden in release_terms")
    if text == "Accepted":
        return
    for part in RELEASE_TERMS_PARTS:
        if part not in text:
            raise ValueError(f"{entry_id}: release_terms missing {part!r}")


def validate_release_record(
    *,
    entry_id: str,
    risk_level: str,
    release_terms: str,
    check_result: str | None,
    check_evidence: str | None,
) -> None:
    """Validate a completed release as a whole (terms + check evidence).

    `Accepted` is legal only for M/L and needs no check. Structured terms
    require `check_result == "pass"` and non-empty `check_evidence`; a `fail`
    result is not a release — the row must stay open.
    """
    validate_release_terms(release_terms, entry_id=entry_id)
    terms = str(release_terms).strip()
    level = str(risk_level).strip()
    if terms == "Accepted":
        if level not in ACCEPTED_RISK_LEVELS:
            raise ValueError(
                f"{entry_id}: Accepted is legal only for M/L (risk_level={level!r}); "
                "H requires release terms plus check evidence"
            )
        return
    result = str(check_result or "").strip()
    evidence = str(check_evidence or "").strip()
    if not result:
        raise ValueError(
            f"{entry_id}: check_result is required to complete a release "
            "(drafted terms are not a release)"
        )
    if result not in CHECK_RESULTS:
        raise ValueError(f"{entry_id}: check_result must be pass|fail (got {result!r})")
    if result == "fail":
        raise ValueError(
            f"{entry_id}: check_result=fail is not a release; keep the row open, "
            "revise terms and re-run the Method, or route RS / human_decision"
        )
    if not evidence:
        raise ValueError(f"{entry_id}: check_evidence is required when check_result=pass")


def _validate_check_fields(entry: dict[str, Any], *, label: str) -> list[str]:
    errors: list[str] = []
    result = entry.get("check_result")
    if result is not None:
        if not isinstance(result, str):
            errors.append(f"{label}.check_result must be a string")
        elif result.strip() not in CHECK_RESULTS:
            errors.append(f"{label}.check_result invalid: {result!r}")
    evidence = entry.get("check_evidence")
    if evidence is not None and not isinstance(evidence, str):
        errors.append(f"{label}.check_evidence must be a string")
    return errors


def validate_registers(
    data: dict[str, Any],
    *,
    r_gate_closed: bool = False,
    r_risk_fields_allowed: bool | None = None,
) -> list[str]:
    if r_risk_fields_allowed is None:
        r_risk_fields_allowed = r_gate_closed
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
                _validate_assumption_entry(
                    entry,
                    index,
                    seen_assumption,
                    r_risk_fields_allowed=True,
                )
            )

    constraints = data.get("constraints")
    if constraints is None:
        pass
    elif not isinstance(constraints, list):
        errors.append("constraints must be an array")
    else:
        seen_constraint: set[str] = set()
        for index, entry in enumerate(constraints):
            errors.extend(_validate_constraint_entry(entry, index, seen_constraint))

    risks = data.get("risks")
    if risks is None:
        pass
    elif not isinstance(risks, list):
        errors.append("risks must be an array")
    else:
        seen_risk: set[str] = set()
        for index, entry in enumerate(risks):
            errors.extend(_validate_risk_entry(entry, index, seen_risk))

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
    r_risk_fields_allowed: bool = True,
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

    if "state" in entry:
        errors.append(f"assumptions[{index}].state retired; use risk_state")

    source = str(entry.get("source", ""))
    if source not in REGISTER_SOURCES:
        errors.append(f"assumptions[{index}].source invalid: {source!r}")

    if not str(entry.get("text", "")).strip():
        errors.append(f"assumptions[{index}].text must be non-empty")

    for retired in ("risk", "consequence", "verification", "disposition"):
        if retired in entry:
            errors.append(f"assumptions[{index}].{retired} retired; use renamed field")

    if "release_tracking" in entry:
        errors.append(f"assumptions[{index}].release_tracking retired")
    if "released" in entry:
        errors.append(f"assumptions[{index}].released retired")

    risk_level = entry.get("risk_level")
    risk_class = entry.get("risk_class")
    risk_state = entry.get("risk_state")
    risk_consequence = entry.get("risk_consequence")
    release_terms = entry.get("release_terms")

    any_risk = any(
        v is not None
        for v in (risk_level, risk_class, risk_state, risk_consequence, release_terms)
    )
    if not any_risk:
        return errors
    # Leftover A# risk_* is dual-read. New writes go to risks[].

    if risk_level is None or risk_class is None or risk_state is None:
        errors.append(
            f"assumptions[{index}]: risk_level, risk_class, and risk_state required together"
        )
        return errors

    level_s = str(risk_level).strip()
    class_s = str(risk_class).strip()
    state_s = str(risk_state).strip()

    if level_s not in RISK_LEVELS:
        errors.append(f"assumptions[{index}].risk_level invalid: {level_s!r}")
    if class_s not in RISK_CLASSES:
        errors.append(f"assumptions[{index}].risk_class invalid: {class_s!r}")
    if state_s not in RISK_STATES:
        errors.append(f"assumptions[{index}].risk_state invalid: {state_s!r}")

    none_count = sum(1 for v in (level_s, class_s, state_s) if v == "none")
    if none_count not in {0, 3}:
        errors.append(
            f"assumptions[{index}]: none triad mismatch "
            f"(risk_level={level_s!r}, risk_class={class_s!r}, risk_state={state_s!r})"
        )
    elif none_count == 0:
        if level_s not in {"H", "M", "L"}:
            errors.append(f"assumptions[{index}].risk_level must be H/M/L for risk rows")
        if class_s not in {"decision", "implementation", "pending"}:
            errors.append(
                f"assumptions[{index}].risk_class must be decision/implementation/pending "
                "for risk rows"
            )
        if state_s not in {"open", "ignore", "completed"}:
            errors.append(
                f"assumptions[{index}].risk_state must be open/ignore/completed for risk rows"
            )

    if risk_consequence is not None and not isinstance(risk_consequence, str):
        errors.append(f"assumptions[{index}].risk_consequence must be a string")
    if release_terms is not None and not isinstance(release_terms, str):
        errors.append(f"assumptions[{index}].release_terms must be a string")
    errors.extend(_validate_check_fields(entry, label=f"assumptions[{index}]"))

    return errors


def _migrate_assumption_entry(entry: dict[str, Any]) -> None:
    if "risk" in entry and "risk_level" not in entry:
        entry["risk_level"] = entry["risk"]
    if "consequence" in entry and "risk_consequence" not in entry:
        entry["risk_consequence"] = entry["consequence"]
    if "verification" in entry and "release_terms" not in entry:
        entry["release_terms"] = entry["verification"]
    if "disposition" in entry and "risk_state" not in entry:
        entry["risk_state"] = entry["disposition"]
    if str(entry.get("risk_class", "")).strip() == "non_risk":
        entry["risk_class"] = "none"
    for key in (
        "risk",
        "consequence",
        "verification",
        "disposition",
        "state",
        "release_tracking",
        "released",
    ):
        entry.pop(key, None)


def _validate_constraint_entry(entry: Any, index: int, seen: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"constraints[{index}] must be an object"]
    entry_id = str(entry.get("id", ""))
    if not re.fullmatch(r"C\d+", entry_id):
        errors.append(f"constraints[{index}].id invalid: {entry_id!r}")
    elif entry_id in seen:
        errors.append(f"duplicate constraint id: {entry_id}")
    else:
        seen.add(entry_id)
    if not str(entry.get("text", "")).strip():
        errors.append(f"constraints[{index}].text must be non-empty")
    revision = entry.get("revision", 1)
    if not isinstance(revision, int) or revision < 1:
        errors.append(f"constraints[{index}].revision invalid: {revision!r}")
    source = str(entry.get("source", ""))
    if source not in REGISTER_SOURCES:
        errors.append(f"constraints[{index}].source invalid: {source!r}")
    return errors


def _validate_risk_entry(entry: Any, index: int, seen: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"risks[{index}] must be an object"]
    entry_id = str(entry.get("id", ""))
    if not re.fullmatch(r"RK\d+", entry_id):
        errors.append(f"risks[{index}].id invalid: {entry_id!r}")
    elif entry_id in seen:
        errors.append(f"duplicate risk id: {entry_id}")
    else:
        seen.add(entry_id)
    source_ref = entry.get("source_ref")
    if not isinstance(source_ref, dict):
        errors.append(f"risks[{index}].source_ref must be an object")
    else:
        kind = str(source_ref.get("kind", "")).strip()
        ref_id = str(source_ref.get("id", "")).strip()
        if kind not in RISK_SOURCE_KINDS:
            errors.append(f"risks[{index}].source_ref.kind invalid: {kind!r}")
        prefix = {"prior": "P", "assumption": "A", "constraint": "C"}.get(kind, "")
        if prefix and not re.fullmatch(rf"{prefix}\d+", ref_id):
            errors.append(f"risks[{index}].source_ref.id invalid: {ref_id!r}")
    if not str(entry.get("text", "")).strip():
        errors.append(f"risks[{index}].text must be non-empty")
    level_s = str(entry.get("risk_level", "")).strip()
    class_s = str(entry.get("risk_class", "")).strip()
    state_s = str(entry.get("risk_state", "")).strip()
    if level_s not in {"H", "M", "L"}:
        errors.append(f"risks[{index}].risk_level must be H/M/L")
    if class_s not in {"decision", "implementation", "pending"}:
        errors.append(f"risks[{index}].risk_class invalid: {class_s!r}")
    if state_s not in {"open", "ignore", "completed"}:
        errors.append(f"risks[{index}].risk_state invalid: {state_s!r}")
    consequence = entry.get("risk_consequence")
    if consequence is not None and not isinstance(consequence, str):
        errors.append(f"risks[{index}].risk_consequence must be a string")
    terms = entry.get("release_terms")
    if terms is not None and not isinstance(terms, str):
        errors.append(f"risks[{index}].release_terms must be a string")
    errors.extend(_validate_check_fields(entry, label=f"risks[{index}]"))
    return errors


def normalize_registers(data: dict[str, Any]) -> dict[str, Any]:
    prior_raw = data.get("prior")
    assumptions_raw = data.get("assumptions")
    constraints_raw = data.get("constraints")
    risks_raw = data.get("risks")
    prior = prior_raw if isinstance(prior_raw, list) else []
    assumptions = assumptions_raw if isinstance(assumptions_raw, list) else []
    constraints = constraints_raw if isinstance(constraints_raw, list) else []
    risks = risks_raw if isinstance(risks_raw, list) else []

    for entry in prior:
        if isinstance(entry, dict) and str(entry.get("source", "")) == "open":
            entry["source"] = "O"
    for entry in assumptions:
        if isinstance(entry, dict):
            if str(entry.get("source", "")) == "open":
                entry["source"] = "O"
            _migrate_assumption_entry(entry)

    return {
        "version": "1",
        "cycle_id": str(data.get("cycle_id", "")),
        "stage": str(data.get("stage", "")),
        "prior": prior,
        "assumptions": assumptions,
        "constraints": constraints,
        "risks": risks,
        "next_prior_seq": int(data.get("next_prior_seq", 1)),
        "next_assumption_seq": int(data.get("next_assumption_seq", 1)),
        "next_constraint_seq": int(data.get("next_constraint_seq", 1)),
        "next_risk_seq": int(data.get("next_risk_seq", 1)),
        "updated_at": data.get("updated_at") or _now_iso(),
    }


def load_registers(
    path: Path,
    *,
    r_gate_closed: bool = False,
    r_risk_fields_allowed: bool | None = None,
) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"registers not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    normalized = normalize_registers(data)
    if r_risk_fields_allowed is None:
        r_risk_fields_allowed = r_gate_closed
    errors = validate_registers(
        normalized,
        r_gate_closed=r_gate_closed,
        r_risk_fields_allowed=r_risk_fields_allowed,
    )
    if errors:
        raise ValueError("; ".join(errors))
    return normalized


def save_registers(
    path: Path,
    data: dict[str, Any],
    *,
    r_gate_closed: bool = False,
    r_risk_fields_allowed: bool | None = None,
) -> dict[str, Any]:
    normalized = normalize_registers(data)
    if r_risk_fields_allowed is None:
        r_risk_fields_allowed = r_gate_closed
    errors = validate_registers(
        normalized,
        r_gate_closed=r_gate_closed,
        r_risk_fields_allowed=r_risk_fields_allowed,
    )
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized["updated_at"] = _now_iso()
    atomic_write_text(
        path,
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
    )
    return normalized


def next_prior_id(data: dict[str, Any]) -> str:
    seq = int(data.get("next_prior_seq", 1))
    return f"P{seq}"


def next_assumption_id(data: dict[str, Any]) -> str:
    seq = int(data.get("next_assumption_seq", 1))
    return f"A{seq}"


def next_constraint_id(data: dict[str, Any]) -> str:
    seq = int(data.get("next_constraint_seq", 1))
    return f"C{seq}"


def next_risk_id(data: dict[str, Any]) -> str:
    seq = int(data.get("next_risk_seq", 1))
    return f"RK{seq}"


def find_duplicate_constraint(data: dict[str, Any], text: str) -> dict[str, Any] | None:
    target = _normalize_text(text)
    for entry in data.get("constraints", []):
        if not isinstance(entry, dict):
            continue
        if _normalize_text(str(entry.get("text", ""))) == target:
            return entry
    return None


def find_risk_by_source(
    data: dict[str, Any], *, kind: str, source_id: str
) -> dict[str, Any] | None:
    for entry in data.get("risks", []):
        if not isinstance(entry, dict):
            continue
        ref = entry.get("source_ref")
        if not isinstance(ref, dict):
            continue
        if str(ref.get("kind", "")) == kind and str(ref.get("id", "")) == source_id:
            return entry
    return None


def find_risk_by_id(data: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    for entry in data.get("risks", []):
        if isinstance(entry, dict) and str(entry.get("id")) == entry_id:
            return entry
    return None


def effective_constraint_text(data: dict[str, Any]) -> str:
    lines = [
        str(entry.get("text", "")).strip()
        for entry in data.get("constraints", [])
        if isinstance(entry, dict) and str(entry.get("text", "")).strip()
    ]
    return "\n".join(lines)


def risk_display_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Assumption rows with RK# overlay, then leftover P/C risks."""
    rows: list[dict[str, Any]] = []
    used: set[str] = set()
    by_assumption: dict[str, dict[str, Any]] = {}
    for entry in data.get("risks", []):
        if not isinstance(entry, dict):
            continue
        ref = entry.get("source_ref")
        if isinstance(ref, dict) and ref.get("kind") == "assumption":
            by_assumption[str(ref.get("id"))] = entry
    for entry in data.get("assumptions", []):
        if not isinstance(entry, dict):
            continue
        row = dict(entry)
        risk = by_assumption.get(str(entry.get("id")))
        if risk is not None:
            used.add(str(risk.get("id")))
            for key in _RISK_FIELD_KEYS:
                if key in risk:
                    row[key] = risk.get(key)
        rows.append(row)
    for entry in data.get("risks", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id")) in used:
            continue
        ref = entry.get("source_ref") if isinstance(entry.get("source_ref"), dict) else {}
        kind = str(ref.get("kind", "")).strip()
        source_id = str(ref.get("id", "")).strip()
        source = f"{kind}:{source_id}" if kind or source_id else ""
        rows.append(
            {
                "id": entry.get("id"),
                "text": entry.get("text"),
                "source": source,
                "risk_level": entry.get("risk_level"),
                "risk_class": entry.get("risk_class"),
                "risk_state": entry.get("risk_state"),
                "risk_consequence": entry.get("risk_consequence"),
                "release_terms": entry.get("release_terms"),
            }
        )
    return rows


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
    source = str(entry.get("source", ""))
    risk_level = entry.get("risk_level")
    risk_class = entry.get("risk_class")
    risk_state = entry.get("risk_state")
    risk_part = f" {risk_level}" if risk_level else ""
    class_part = f"/{risk_class}" if risk_class else ""
    state_part = f"/{risk_state}" if risk_state else ""
    return f"[{entry.get('id')} {source}{risk_part}{class_part}{state_part}] {entry.get('text')}"

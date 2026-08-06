#!/usr/bin/env python3
"""Schema and render for decision-eval-target.md (Eval generation rule)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dec_decision_doc_schema import SECTION_HEADINGS, SECTION_ORDER
from dec_domain_constraints_schema import is_section_active
from dec_gate_payload_schema import gate_payloads_for_session
from dec_io import atomic_write_text
from dec_register_schema import load_registers

EVAL_TARGET_FILENAME = "decision-eval-target.md"

_SECTION_SOURCE: dict[str, str] = {
    "user_prior": "registers.json#prior",
    "problem": "gate-payloads/Q.json",
    "direction": "gate-payloads/E.json",
    "settled_direction": "gate-payloads/D.json",
    "assumptions": "registers.json#assumptions",
    "execution_analysis": "gate-payloads/X.json",
}

_SECTION_GATE: dict[str, str | None] = {
    "user_prior": None,
    "problem": "Q",
    "direction": "E",
    "settled_direction": "D",
    "assumptions": None,
    "execution_analysis": "X",
}


def eval_target_path(session_dir: Path) -> Path:
    return session_dir / EVAL_TARGET_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("\n", " ").strip()


def _render_kv_block(fields: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"- {key}:")
            if not value:
                lines.append("  - _(empty)_")
                continue
            for item in value:
                if isinstance(item, dict):
                    lines.append("  -")
                    for nested_key, nested_val in item.items():
                        lines.append(f"    {nested_key}: {_scalar(nested_val)}")
                else:
                    lines.append(f"  - {_scalar(item)}")
        else:
            lines.append(f"- {key}: {_scalar(value)}")
    return "\n".join(lines)


def _render_prior_table(prior: list[Any]) -> str:
    lines = [
        "| id | kind | state | source | text |",
        "|----|------|-------|--------|------|",
    ]
    if not prior:
        lines.append("| | | | | |")
        return "\n".join(lines)
    for entry in prior:
        if not isinstance(entry, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _scalar(entry.get("id", "")),
                    _scalar(entry.get("kind", "")),
                    _scalar(entry.get("state", "")),
                    _scalar(entry.get("source", "")),
                    _scalar(entry.get("text", "")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _render_assumptions_table(assumptions: list[Any]) -> str:
    lines = [
        "| id | text | source | risk_level | risk_class | risk_state | release_terms | risk_consequence |",
        "|----|------|--------|------------|------------|------------|---------------|------------------|",
    ]
    if not assumptions:
        lines.append("| | | | | | | | |")
        return "\n".join(lines)
    for entry in assumptions:
        if not isinstance(entry, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _scalar(entry.get("id", "")),
                    _scalar(entry.get("text", "")),
                    _scalar(entry.get("source", "")),
                    _scalar(entry.get("risk_level", entry.get("risk", ""))),
                    _scalar(entry.get("risk_class", "")),
                    _scalar(entry.get("risk_state", entry.get("disposition", ""))),
                    _scalar(entry.get("release_terms", entry.get("verification", ""))),
                    _scalar(
                        entry.get("risk_consequence", entry.get("consequence", ""))
                    ),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _section_body(
    section_key: str,
    *,
    payloads: dict[str, dict[str, Any]],
    registers: dict[str, Any],
) -> str:
    if section_key == "user_prior":
        return _render_prior_table(list(registers.get("prior") or []))
    if section_key == "assumptions":
        return _render_assumptions_table(list(registers.get("assumptions") or []))
    gate = _SECTION_GATE[section_key]
    assert gate is not None
    payload = payloads.get(gate) or {}
    if section_key == "problem":
        return _render_kv_block(
            {
                "problem_statement": payload.get("problem_statement", ""),
                "constraints": payload.get("constraints", ""),
            }
        )
    if section_key == "direction":
        return _render_kv_block(
            {
                "user_choice": payload.get("user_choice", ""),
                "directions": payload.get("directions") or [],
                "excluded": payload.get("excluded") or [],
            }
        )
    if section_key == "settled_direction":
        return _render_kv_block(
            {
                "decision_rationale": payload.get("decision_rationale", ""),
                "applies_to": payload.get("applies_to", ""),
                "excludes": payload.get("excludes", ""),
                "execution_approach": payload.get("execution_approach", ""),
            }
        )
    if section_key == "execution_analysis":
        return _render_kv_block(
            {
                "acceptance_criteria": payload.get("acceptance_criteria", ""),
                "gap": payload.get("gap", "None"),
                "impact_surface": payload.get("impact_surface") or [],
                "external_dependencies": payload.get("external_dependencies") or [],
                "key_changes": payload.get("key_changes", ""),
                "critical_constraints": payload.get("critical_constraints", ""),
                "reversibility": payload.get("reversibility", ""),
            }
        )
    raise ValueError(f"unsupported section_key: {section_key!r}")


def expected_sections(constraints: dict[str, Any]) -> list[str]:
    return [key for key in SECTION_ORDER if is_section_active(constraints, key)]


def validate_eval_target_inputs(
    *,
    payloads: dict[str, dict[str, Any]],
    registers: dict[str, Any],
    constraints: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(registers, dict):
        errors.append("registers must be an object")
    for section_key in expected_sections(constraints):
        gate = _SECTION_GATE[section_key]
        if gate is None:
            continue
        if gate not in payloads:
            errors.append(f"missing gate payload for section {section_key}: {gate}.json")
    return errors


def render_eval_target(
    *,
    cycle_id: str,
    stage: str,
    payloads: dict[str, dict[str, Any]],
    registers: dict[str, Any],
    constraints: dict[str, Any],
    sealed_at: str | None = None,
) -> str:
    errors = validate_eval_target_inputs(
        payloads=payloads,
        registers=registers,
        constraints=constraints,
    )
    if errors:
        raise ValueError("; ".join(errors))

    stamp = sealed_at or _now_iso()
    parts = [
        "# Decision EvalTarget",
        "",
        f"- cycle_id: {cycle_id}",
        f"- stage: {stage}",
        f"- sealed_at: {stamp}",
        "",
    ]
    for section_key in expected_sections(constraints):
        heading = SECTION_HEADINGS[section_key]
        source = _SECTION_SOURCE[section_key]
        body = _section_body(section_key, payloads=payloads, registers=registers)
        parts.extend(
            [
                f"<!-- chapter:{section_key} -->",
                heading,
                f"source: {source}",
                "",
                body,
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def save_eval_target(path: Path, content: str) -> None:
    atomic_write_text(path, content)


def render_and_save_eval_target(
    session_dir: Path,
    *,
    cycle_id: str,
    stage: str,
    constraints: dict[str, Any],
    r_gate_closed: bool = True,
) -> Path:
    paths_payloads = gate_payloads_for_session(session_dir / "gate-payloads")
    registers = load_registers(
        session_dir / "registers.json",
        r_gate_closed=r_gate_closed,
    )
    content = render_eval_target(
        cycle_id=cycle_id,
        stage=stage,
        payloads=paths_payloads,
        registers=registers,
        constraints=constraints,
    )
    out = eval_target_path(session_dir)
    save_eval_target(out, content)
    return out

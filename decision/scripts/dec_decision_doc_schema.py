#!/usr/bin/env python3
"""Schema and I/O for diagnostic decision-doc.md section patching."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dec_io import atomic_write_text

from dec_domain_constraints_schema import (  # noqa: WPS433
    ALL_X_DIMENSIONS,
    active_x_dimensions,
    is_section_active,
    omitted_sections,
)

SECTION_HEADINGS: dict[str, str] = {
    "user_prior": "## 1. User Prior",
    "problem": "## 2. Problem Definition",
    "direction": "## 3. Direction Comparison",
    "decision_rationale": "## 4. Decision Rationale",
    "scope": "## 5. Scope",
    "assumptions": "## 6. Assumptions & Risks",
    "execution_analysis": "## 7. Execution Analysis",
}

SECTION_ORDER: tuple[str, ...] = (
    "user_prior",
    "problem",
    "direction",
    "decision_rationale",
    "scope",
    "assumptions",
    "execution_analysis",
)

GATE_SECTION_KEYS: dict[str, tuple[str, ...]] = {
    "Q": ("problem",),
    "E": ("direction",),
    "D": ("decision_rationale", "scope"),
    "X": ("execution_analysis",),
    "R": (),
}

GATE_CLOSE_PREREQ: dict[str, str | None] = {
    "Q": "O",
    "E": "Q",
    "D": "E",
    "X": "D",
    "R": "X",
    "V": "R",
    "RR": "V",
}


def init_decision_doc(
    *,
    template: str,
    cycle_id: str,
    title: str = "TBD",
    constraints: dict[str, Any] | None = None,
) -> str:
    doc = template
    doc = doc.replace("{title}", title)
    doc = doc.replace("{one-line summary of the intent input}", f"Cycle {cycle_id}")
    if constraints is not None:
        doc = strip_sections(doc, omitted_sections(constraints))
    return doc


def strip_sections(doc: str, omitted: frozenset[str]) -> str:
    updated = doc
    for key in reversed(SECTION_ORDER):
        if key not in omitted:
            continue
        heading = SECTION_HEADINGS.get(key)
        if not heading:
            continue
        pattern = _heading_pattern(heading)
        match = pattern.search(updated)
        if not match:
            continue
        start = match.start()
        end = _section_end_index(updated, match.end())
        updated = (updated[:start].rstrip() + "\n\n" + updated[end:].lstrip()).strip()
    return updated + "\n"


def _heading_pattern(heading: str) -> re.Pattern[str]:
    escaped = re.escape(heading)
    return re.compile(rf"^{escaped}\s*$", re.MULTILINE)


def _section_end_index(text: str, start: int) -> int:
    for match in re.finditer(r"^## \d+\.", text[start + 1 :], re.MULTILINE):
        return start + 1 + match.start()
    return len(text)


def replace_section(
    doc: str,
    section_key: str,
    body: str,
    *,
    constraints: dict[str, Any] | None = None,
) -> str:
    if constraints is not None and not is_section_active(constraints, section_key):
        return doc
    heading = SECTION_HEADINGS.get(section_key)
    if heading is None:
        raise ValueError(f"unsupported section_key: {section_key!r}")
    pattern = _heading_pattern(heading)
    match = pattern.search(doc)
    if not match:
        raise ValueError(f"section heading not found: {heading}")
    start = match.end()
    end = _section_end_index(doc, start)
    normalized_body = body.strip()
    replacement = f"\n\n{normalized_body}\n\n"
    return doc[:start] + replacement + doc[end:].lstrip("\n")


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def render_user_prior_body(registers: dict[str, Any]) -> str:
    lines: list[str] = []
    prior = registers.get("prior", [])
    if not prior:
        lines.append("- _(none yet)_")
    else:
        for entry in prior:
            if not isinstance(entry, dict):
                continue
            kind = str(entry.get("kind", "judgment"))
            text = str(entry.get("text", "")).strip()
            lines.append(f"- [{kind}] {text}")
    return "\n".join(lines)


def render_problem_body(*, problem_statement: str, constraints: str) -> str:
    return (
        f"{problem_statement.strip()}\n\n"
        f"**Known Constraints:** {constraints.strip()}"
    )


def render_direction_body(
    *,
    directions: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    user_choice: str,
) -> str:
    lines = [
        "| Direction | Core Approach | Pros | Cons |",
        "|-----------|--------------|------|------|",
    ]
    for item in directions:
        name = _escape_cell(str(item.get("name", "")))
        if item.get("recommended"):
            name = f"**{name}** (recommended)"
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    _escape_cell(str(item.get("approach", ""))),
                    _escape_cell(str(item.get("pros", ""))),
                    _escape_cell(str(item.get("cons", ""))),
                ]
            )
            + " |"
        )
    lines.extend(["", "**Excluded Directions:**", ""])
    if excluded:
        lines.extend(
            [
                "| Direction | Reason for Exclusion |",
                "|-----------|---------------------|",
            ]
        )
        for item in excluded:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(str(item.get("name", ""))),
                        _escape_cell(str(item.get("reason", ""))),
                    ]
                )
                + " |"
            )
    else:
        lines.append("_None_")
    lines.extend(["", f"**User Choice:** {user_choice.strip()}"])
    return "\n".join(lines)


def render_decision_rationale_body(*, rationale: str) -> str:
    return rationale.strip()


def render_scope_body(
    *,
    applies_to: str,
    excludes: str,
    execution_approach: str,
) -> str:
    return (
        f"**Applies to:** {applies_to.strip()}\n\n"
        f"**Explicitly excludes:** {excludes.strip()}\n\n"
        f"**Execution Approach:** {execution_approach.strip()}"
    )


def render_execution_analysis_body(
    *,
    acceptance_criteria: str,
    gap: str,
    impact_surface: list[dict[str, Any]],
    external_dependencies: list[dict[str, Any]],
    key_changes: str,
    critical_constraints: str,
    reversibility: str,
    x_dimensions: frozenset[str] | None = None,
) -> str:
    dims = x_dimensions or frozenset(ALL_X_DIMENSIONS)
    lines: list[str] = []

    if "acceptance_criteria" in dims or "gap_check" in dims:
        lines.extend(["### 7.1 Acceptance Criteria", ""])
        if "acceptance_criteria" in dims:
            lines.append(acceptance_criteria.strip())
        else:
            lines.append("_Omitted per domain constraints_")
        if "gap_check" in dims:
            lines.extend(["", f"**Gap (if any):** {gap.strip() or 'None'}"])
        lines.append("")

    if "impact_surface" in dims:
        lines.extend(
            [
                "### 7.2 Impact Surface",
                "",
                "| Layer | Affected Area | Change Type | Notes |",
                "|-------|--------------|-------------|-------|",
            ]
        )
        if impact_surface:
            for row in impact_surface:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _escape_cell(str(row.get("layer", ""))),
                            _escape_cell(str(row.get("area", ""))),
                            _escape_cell(str(row.get("change_type", ""))),
                            _escape_cell(str(row.get("notes", ""))),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("| | | | |")
        lines.append("")

    if "external_dependencies" in dims:
        lines.extend(
            [
                "### 7.3 External Dependencies",
                "",
                "| Dependency | Contract | Authoritative Source | Confirmation Mechanism |",
                "|------------|----------|---------------------|------------------------|",
            ]
        )
        if external_dependencies:
            for row in external_dependencies:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _escape_cell(str(row.get("dependency", ""))),
                            _escape_cell(str(row.get("contract", ""))),
                            _escape_cell(str(row.get("source", ""))),
                            _escape_cell(str(row.get("confirmation", ""))),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("| | | | |")
        lines.append("")

    if "implementation_sketch" in dims:
        lines.extend(
            [
                "### 7.4 Implementation Sketch",
                "",
                f"**Key changes:** {key_changes.strip()}",
                f"**Critical constraints:** {critical_constraints.strip()}",
                f"**Reversibility:** {reversibility.strip()}",
            ]
        )

    if not lines:
        return "_No X dimensions active per domain constraints_"
    return "\n".join(lines).strip()


def render_assumptions_body(registers: dict[str, Any]) -> str:
    lines = [
        "> Status values: `[待验证]` · `[已验证]` · `[失效]`",
        "",
        "| # | Assumption | Source | Risk | Release Tracking | Failure Consequence | Verification | Status |",
        "|---|-----------|--------|------|------------------|---------------------|-------------|--------|",
    ]
    assumptions = registers.get("assumptions", [])
    if not assumptions:
        lines.append("| | | | | | | | |")
    else:
        for entry in assumptions:
            if not isinstance(entry, dict):
                continue
            state = str(entry.get("state", "pending"))
            status = "[已验证]" if state == "verified" else "[待验证]"
            risk = entry.get("risk") or ""
            tracking = "Yes" if entry.get("release_tracking") else ""
            verification = entry.get("verification") or ""
            consequence = entry.get("consequence") or ""
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(str(entry.get("id", ""))),
                        _escape_cell(str(entry.get("text", ""))),
                        _escape_cell(str(entry.get("source", ""))),
                        _escape_cell(str(risk)),
                        _escape_cell(tracking),
                        _escape_cell(str(consequence)),
                        _escape_cell(str(verification)),
                        _escape_cell(status),
                    ]
                )
                + " |"
            )
    return "\n".join(lines)


def _section_placeholders() -> dict[str, str]:
    return {
        "problem": render_problem_body(problem_statement="TBD", constraints="TBD"),
        "direction": render_direction_body(directions=[], excluded=[], user_choice="TBD"),
        "decision_rationale": "TBD",
        "scope": render_scope_body(
            applies_to="TBD",
            excludes="TBD",
            execution_approach="TBD",
        ),
        "execution_analysis": render_execution_analysis_body(
            acceptance_criteria="TBD",
            gap="None",
            impact_surface=[],
            external_dependencies=[],
            key_changes="TBD",
            critical_constraints="TBD",
            reversibility="TBD",
        ),
    }


def clear_sections_from_gate(doc: str, gate: str) -> str:
    keys = GATE_SECTION_KEYS.get(gate, ())
    updated = doc
    placeholders = _section_placeholders()
    for key in keys:
        if key in placeholders:
            updated = replace_section(updated, key, placeholders[key])
    return updated


def clear_sections_downstream(doc: str, from_gate: str) -> str:
    from dec_gate_state_schema import downstream_gates  # noqa: WPS433

    updated = doc
    for gate in downstream_gates(from_gate):
        if gate in GATE_SECTION_KEYS:
            updated = clear_sections_from_gate(updated, gate)
    return updated


def check_decision_doc_ready(
    doc: str,
    *,
    constraints: dict[str, Any] | None = None,
) -> list[str]:
    """Return delivery readiness errors for decision-doc content."""
    errors: list[str] = []
    for key in ("problem", "direction", "decision_rationale", "scope", "execution_analysis"):
        if constraints is not None and not is_section_active(constraints, key):
            continue
        heading = SECTION_HEADINGS[key]
        pattern = _heading_pattern(heading)
        match = pattern.search(doc)
        if not match:
            errors.append(f"missing section: {heading}")
            continue
        start = match.end()
        end = _section_end_index(doc, start)
        body = doc[start:end].strip()
        if not body or body == "TBD" or "TBD" in body[:80]:
            errors.append(f"section not ready: {heading}")
    return errors


def load_decision_doc(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"decision-doc not found: {path}")
    return path.read_text(encoding="utf-8")


def save_decision_doc(path: Path, content: str) -> None:
    atomic_write_text(path, content)

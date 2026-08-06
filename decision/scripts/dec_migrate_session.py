#!/usr/bin/env python3
"""Migrate legacy decision sessions (pre gate-state) to incremental architecture."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from workflow_sessions import parse_frontmatter  # noqa: E402

from dec_decision_doc_schema import (
    SECTION_HEADINGS,
    _heading_pattern,
    _section_end_index,
    load_decision_doc,
)
from dec_domain_constraints_schema import (
    default_kernel_constraints,
    load_constraints_config,
    load_domain_constraints,
    save_domain_constraints,
)
from dec_gate_state_schema import GATE_ORDER, init_gate_state, save_gate_state
from dec_register_schema import init_registers, save_registers


_GATE_AFTER_SECTION: tuple[tuple[str, str], ...] = (
    ("Q", "problem"),
    ("E", "direction"),
    ("D", "settled_direction"),
    ("X", "execution_analysis"),
)


def needs_migration(session_dir: Path) -> bool:
    ss = session_dir / "session-state.md"
    gs = session_dir / "gate-state.json"
    return ss.exists() and not gs.exists()


def _section_body(doc: str, section_key: str) -> str:
    heading = SECTION_HEADINGS[section_key]
    match = _heading_pattern(heading).search(doc)
    if not match:
        return ""
    start = match.end()
    end = _section_end_index(doc, start)
    return doc[start:end].strip()


def _section_ready(body: str) -> bool:
    if not body or body == "TBD":
        return False
    if "TBD" in body[:80]:
        return False
    if body.startswith("_(") and "none yet" in body.lower():
        return False
    return True


def infer_progress(
    doc: str,
    *,
    constraints: dict[str, Any],
    delivered: bool,
) -> tuple[str, list[str]]:
    """Return (active_gate, skipped_gates) from decision-doc content."""
    if delivered:
        return "DC", []

    last_closed = "O"
    for gate, section_key in _GATE_AFTER_SECTION:
        body = _section_body(doc, section_key)
        if not _section_ready(body):
            break
        last_closed = gate

    idx = GATE_ORDER.index(last_closed)
    if idx + 1 < len(GATE_ORDER):
        return GATE_ORDER[idx + 1], []
    return last_closed, []


def build_gate_state_from_progress(
    *,
    cycle_id: str,
    stage: str,
    active_gate: str,
    skipped_gates: list[str],
    delivered: bool,
) -> dict[str, Any]:
    state = init_gate_state(cycle_id=cycle_id, stage=stage)
    if delivered:
        for gate in GATE_ORDER:
            state["gates"][gate]["status"] = "closed"
        state["active_gate"] = "DC"
        state["skipped_gates"] = list(skipped_gates)
        return state

    active_idx = GATE_ORDER.index(active_gate)
    for idx, gate in enumerate(GATE_ORDER):
        if idx < active_idx:
            state["gates"][gate]["status"] = "closed"
        elif idx == active_idx:
            state["gates"][gate]["status"] = "active"
        else:
            state["gates"][gate]["status"] = "pending"
    state["active_gate"] = active_gate
    state["skipped_gates"] = list(skipped_gates)
    return state


def _parse_prior_from_doc(doc: str) -> list[dict[str, Any]]:
    body = _section_body(doc, "user_prior")
    entries: list[dict[str, Any]] = []
    for line in body.splitlines():
        match = re.match(r"^-\s*\[(?P<kind>[^\]]+)\]\s*(?P<text>.+)$", line.strip())
        if not match:
            continue
        seq = len(entries) + 1
        entries.append(
            {
                "id": f"P{seq}",
                "kind": match.group("kind").strip(),
                "text": match.group("text").strip(),
                "state": "pending",
                "source": "O",
            }
        )
    return entries


def _parse_assumptions_from_doc(doc: str) -> list[dict[str, Any]]:
    body = _section_body(doc, "assumptions")
    entries: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or not re.fullmatch(r"A\d+", cells[0]):
            continue
        # 9 cols: + Class; 8 cols: + Release Tracking; 7 cols: legacy
        risk_class_val = None
        if len(cells) >= 9:
            (
                entry_id,
                text,
                source,
                risk,
                risk_class,
                tracking,
                consequence,
                verification,
                status,
            ) = cells[:9]
            risk_class_val = (
                risk_class
                if risk_class in {"decision", "implementation", "pending"}
                else None
            )
        elif len(cells) >= 8:
            entry_id, text, source, risk, tracking, consequence, verification, status = cells[:8]
        elif len(cells) >= 7:
            entry_id, text, source, risk, consequence, verification, status = cells[:7]
            tracking = ""
        else:
            continue
        if "已交接" in status:
            # Legacy Handoff status must not become completed (D6/D17).
            risk_state = "open"
        elif "已验证" in status or "completed" in status.lower():
            risk_state = "completed"
        elif "忽略" in status:
            risk_state = "ignore"
        else:
            risk_state = "open"
        risk_val = risk if risk in {"H", "M", "L"} else None
        if risk_val is None and risk_class_val is None:
            risk_level = "none"
            risk_class_val = "none"
            risk_state = "none"
        else:
            risk_level = risk_val or "none"
            risk_class_val = risk_class_val or "pending"
        entry: dict[str, Any] = {
            "id": entry_id,
            "text": text,
            "source": source or "O",
            "risk_level": risk_level,
            "risk_class": risk_class_val,
            "risk_state": risk_state,
            "risk_consequence": consequence or None,
            "release_terms": verification or None,
        }
        entries.append(entry)
    return entries


def build_registers_from_doc(
    doc: str,
    *,
    cycle_id: str,
    stage: str,
) -> dict[str, Any]:
    registers = init_registers(cycle_id=cycle_id, stage=stage)
    prior = _parse_prior_from_doc(doc)
    assumptions = _parse_assumptions_from_doc(doc)
    registers["prior"] = prior
    registers["assumptions"] = assumptions
    registers["next_prior_seq"] = len(prior) + 1
    registers["next_assumption_seq"] = len(assumptions) + 1
    return registers


def migrate_session_dir(
    session_dir: Path,
    *,
    project_root: Path,
    cycle_id: str,
    stage: str,
    constraints_path: Path | None = None,
) -> dict[str, Any]:
    if not needs_migration(session_dir):
        raise ValueError("session does not require migration")

    doc_path = session_dir / "decision-doc.md"
    ss_path = session_dir / "session-state.md"
    doc = load_decision_doc(doc_path) if doc_path.exists() else ""

    fm = parse_frontmatter(ss_path.read_text(encoding="utf-8"))
    delivered = fm.get("current_state") in {"Completed", "Delivered"}

    dc_path = session_dir / "domain-constraints.json"
    if dc_path.is_file():
        constraints = load_domain_constraints(dc_path)
    else:
        if constraints_path is not None:
            constraints = load_constraints_config(constraints_path, stage=stage)
        else:
            constraints = default_kernel_constraints(stage=stage)
    save_domain_constraints(dc_path, constraints)

    active_gate, skipped = infer_progress(doc, constraints=constraints, delivered=delivered)
    gate_state = build_gate_state_from_progress(
        cycle_id=cycle_id,
        stage=stage,
        active_gate=active_gate,
        skipped_gates=skipped,
        delivered=delivered,
    )
    save_gate_state(session_dir / "gate-state.json", gate_state)

    r_closed = gate_state["gates"]["R"]["status"] == "closed"
    registers = build_registers_from_doc(doc, cycle_id=cycle_id, stage=stage) if doc else init_registers(
        cycle_id=cycle_id,
        stage=stage,
    )
    save_registers(session_dir / "registers.json", registers, r_gate_closed=r_closed)

    return {
        "active_gate": gate_state["active_gate"],
        "delivered": delivered,
        "prior_count": len(registers.get("prior", [])),
        "assumption_count": len(registers.get("assumptions", [])),
    }

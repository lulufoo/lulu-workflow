#!/usr/bin/env python3
"""Inductive runner outer gate spine control.

Manages the G1->G2->G3->G4 gate state machine for the inductive runner.
Delegates all G3 section / EP operations to inductive_g3_section_control.py
via subprocess ($INDUCTIVE_G3_SECTION_CTL). G2/G3 grounding reads are
facade subcommands that subprocess to artifact controls.

Subcommands:
    init-session        Seed gate state + delegate init-pointer to section control
    resolve-context     Return active_gate, active_section, open-EP count,
                        architecture_view summary (multi-turn resume entry point)
    gate-close          Close a gate with payload validation and prereq check
    gate-reopen         Reopen a gate; downstream gates reset to pending
                        (also deletes the stale g2/g4 report where applicable).
                        --sections is accepted only with --gate G3: atomically
                        rewinds each listed section (subprocess to section
                        control) in the same call, so a G3 reopen can never be
                        left half-paired (gate reopened, section still 'cleared').
    g2-check-report     Facade: subprocess to inductive_g2_control check-g2-report
    g2-list-report      Facade: subprocess to inductive_g2_control list-g2-report
    grounding-check     Facade: subprocess to inductive_g3_grounding_control (shallow)
    grounding-list      Facade: subprocess to inductive_g3_grounding_control (shallow)
    deep-grounding-list Facade: subprocess to inductive_g3_grounding_control
                        (mode=deep, one open point via --ep-id)
    g4-check-report     Facade: subprocess to inductive_g4_control check-recompose-report
    g4-list-report      Facade: subprocess to inductive_g4_control list-recompose-report

Payload per gate:
    G1: {"user_confirmed": true} required; architecture_view/shape_constraints optional resume aid only
    G2: {}  (absent report auto-passes; present report requires verdict=ok)
    G3: must pass check-coverage (delegated to section control)
    G4: none accepted from the caller — report-driven. gate-close internally
        merges structural {reforms_shape, shape_absorbed} (recompose-check)
        with semantic {conflicts, buildable, reversible, verifiable}
        (g4-recompose-report.json via g4-recompose-runner) and validates that.

All subcommands print JSON to stdout and exit 0 on success, exit 1 on failure.

Global flag: --out-dir PATH (required for all subcommands)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from active_context_schema import resolve_conversation_id  # noqa: E402
from platform_schema import detect_platform  # noqa: E402

from inductive_gate_state_schema import (  # noqa: E402
    GATE_ORDER,
    close_gate,
    header_gate_symbols,
    init_gate_state,
    is_gate_closed,
    load_gate_state,
    reopen_gate,
    save_gate_state,
)


_CURSOR_CONVERSATION_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _cursor_conversation_id_valid(conv_id: str) -> bool:
    return bool(_CURSOR_CONVERSATION_UUID.match(conv_id.strip()))

def _gate_state_path(out_dir: Path) -> Path:
    return out_dir / "inductive-gate-state.json"


def _dqi_path(out_dir: Path) -> Path:
    return out_dir / "inductive-dqi.json"


def _section_ctl(out_dir: Path) -> list[str]:
    """Return the base argv for invoking inductive_g3_section_control.py."""
    script = _HERE / "inductive_g3_section_control.py"
    return [sys.executable, str(script), "--out-dir", str(out_dir)]


def _g2_ctl(out_dir: Path) -> list[str]:
    script = _HERE / "inductive_g2_control.py"
    return [sys.executable, str(script), "--out-dir", str(out_dir)]


def _g3_grounding_ctl(out_dir: Path) -> list[str]:
    script = _HERE / "inductive_g3_grounding_control.py"
    return [sys.executable, str(script), "--out-dir", str(out_dir)]


def _g4_ctl(out_dir: Path) -> list[str]:
    script = _HERE / "inductive_g4_control.py"
    return [sys.executable, str(script), "--out-dir", str(out_dir)]


def _run_section_ctl(out_dir: Path, *extra_args: str) -> dict[str, Any]:
    """Run section control subcommand and return parsed JSON stdout."""
    cmd = _section_ctl(out_dir) + list(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": result.stdout or result.stderr}


def _forward_ctl(base_argv: list[str], *extra_args: str) -> None:
    """Run a child control CLI and forward stdout/exit code unchanged."""
    cmd = base_argv + list(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        sys.stdout.write(result.stdout)
        if not result.stdout.endswith("\n"):
            sys.stdout.write("\n")
    elif result.returncode != 0:
        message = result.stderr.strip() or "subprocess failed"
        print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    if result.returncode != 0:
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_init_session(out_dir: Path, args: argparse.Namespace) -> None:
    gate_path = _gate_state_path(out_dir)
    if gate_path.exists():
        _fail(f"gate state already exists: {gate_path}; use resolve-context to resume")

    master_conv = resolve_conversation_id(getattr(args, "conversation_id", "") or "") or ""
    if detect_platform() == "cursor" and not master_conv:
        _fail(
            "init-session failed: platform session identity missing; "
            "retry the same command without extra shell flags."
        )
    if detect_platform() == "cursor" and not _cursor_conversation_id_valid(master_conv):
        _fail(
            "init-session failed: invalid platform session identity; "
            "retry the same command without extra shell flags."
        )

    cycle_id = args.cycle_id or ""
    stage = args.stage or ""
    state = init_gate_state(
        cycle_id=cycle_id,
        stage=stage,
        master_conversation_id=master_conv,
    )
    save_gate_state(gate_path, state)

    # Delegate section pointer + EP ledger init
    sections: str = args.sections or ""
    mandatory: str = args.mandatory or ""

    ptr_result = _run_section_ctl(
        out_dir,
        "init-pointer",
        "--sections", sections,
        "--mandatory", mandatory,
        "--cycle-id", cycle_id,
    )
    if not ptr_result.get("ok"):
        _fail("section pointer init failed: " + ptr_result.get("error", "unknown"))

    _ok({
        "message": "session initialized",
        "active_gate": "G1",
        "sections": sections,
        "mandatory": mandatory,
    })


def cmd_resolve_context(out_dir: Path, _args: argparse.Namespace) -> None:
    """Multi-turn resume entry point: aggregate gate + section state."""
    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)
    symbols = header_gate_symbols(state)

    section_status: dict[str, Any] = {}
    frontier: dict[str, Any] = {}
    active_section = None
    open_ep_count = 0

    if state["active_gate"] in {"G3", "G4"}:
        sec_result = _run_section_ctl(out_dir, "status")
        if sec_result.get("ok"):
            section_status = sec_result.get("sections", {})
            frontier = sec_result.get("frontier", {})
            active_section = sec_result.get("active_section")
            open_ep_count = sec_result.get("open_blocking_ep_count", 0)

    architecture_view = None
    dqi_p = _dqi_path(out_dir)
    if dqi_p.exists():
        try:
            dqi = json.loads(dqi_p.read_text(encoding="utf-8"))
            architecture_view = dqi.get("architecture_view")
        except Exception:
            pass

    _ok({
        "active_gate": state["active_gate"],
        "gate_symbols": symbols,
        "gates": {g: state["gates"][g]["status"] for g in GATE_ORDER},
        "active_section": active_section,
        "section_statuses": section_status,
        "frontier": frontier,
        "open_blocking_ep_count": open_ep_count,
        "architecture_view": architecture_view,
    })


def cmd_gate_close(out_dir: Path, args: argparse.Namespace) -> None:
    gate: str = args.gate.upper()
    if gate not in GATE_ORDER:
        _fail(f"invalid gate: {gate!r}; must be one of {GATE_ORDER}")

    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)

    # Guard: gate must be the current active gate
    if state.get("active_gate") != gate:
        _fail(
            f"cannot close gate {gate!r}: active gate is {state.get('active_gate')!r}; "
            "switch to the correct gate first or call gate-reopen to reset"
        )

    # Guard: gate must not already be closed
    if is_gate_closed(state, gate):
        _fail(f"gate {gate!r} is already closed")

    # Prereq: all previous gates must be closed
    idx = GATE_ORDER.index(gate)
    for prev in GATE_ORDER[:idx]:
        if not is_gate_closed(state, prev):
            _fail(f"prereq not met: gate {prev!r} must be closed before closing {gate!r}")

    # Parse payload
    payload: dict[str, Any] = {}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            _fail(f"invalid payload JSON: {exc}")

    # Gate-specific validation
    if gate == "G1":
        _validate_g1_payload(payload)
    elif gate == "G2":
        _validate_g2_close(out_dir)
    elif gate == "G3":
        _validate_g3_close(out_dir)
    elif gate == "G4":
        # G4 is report-driven: any caller-supplied --payload is ignored in favor
        # of the merged structural (recompose-check) + semantic (g4-recompose-runner
        # report) predicates, so gate-close can never be satisfied by AI-recalled
        # field values.
        payload = _validate_g4_close(out_dir)

    # Close the gate and persist
    updated = close_gate(state, gate, payload=payload if payload else None)
    save_gate_state(gate_path, updated)

    # For G1: write architecture_view to DQI (legacy resume aid) + shape checkpoint mark
    if gate == "G1":
        if payload.get("architecture_view"):
            _write_dqi_field(out_dir, "architecture_view", payload["architecture_view"])
            _write_dqi_field(
                out_dir, "shape_constraints", payload.get("shape_constraints", [])
            )
        # section-SoT: Shape-confirm baseline = _index.last_checkpoint == "shape"
        _run_section_ctl(out_dir, "checkpoint", "--name", "shape")

    # For G4: write merged recompose_check to DQI
    if gate == "G4":
        _write_dqi_field(out_dir, "recompose_check", payload)

    _ok({
        "closed": gate,
        "active_gate": updated["active_gate"],
    })


# ---------------------------------------------------------------------------
# Gate-specific payload validators
# ---------------------------------------------------------------------------

def _validate_g1_payload(payload: dict[str, Any]) -> None:
    """Shape-confirm close: user confirmation is hard; DQI view is optional aid.

    Design §7 / I11: authoritative baseline is ``checkpoint("shape")``, not a
    frozen ``architecture_view``. If a resume-aid view is supplied, it must be
    complete; absence is allowed.
    """
    if not payload.get("user_confirmed"):
        _fail("G1 payload must include 'user_confirmed': true")
    av = payload.get("architecture_view")
    if av is None:
        return
    if not isinstance(av, dict):
        _fail("architecture_view must be an object when provided")
    required = ("as_is", "to_be", "scope", "spine", "traces_to")
    missing = [f for f in required if not av.get(f)]
    if missing:
        _fail(f"architecture_view missing fields: {missing}")


def _validate_g2_close(out_dir: Path) -> None:
    """G2 folded into per-open attach-code-refs (design Turn 44 / plan C2).

    If ``g2-topology-report.json`` is absent → auto-pass (independent G2 gate
    no longer required; Shape-confirm + Audit cover the early global check).
    If present → still require ``verdict=ok`` (legacy / optional topology pass).
    """
    report_path = Path(out_dir) / "g2-topology-report.json"
    if not report_path.exists():
        return

    cmd = _g2_ctl(out_dir) + ["check-g2-report"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        _fail(result.stdout or result.stderr or "G2 gate-close rejected: g2 check failed")
    if result.returncode != 0 or not payload.get("ok"):
        _fail(payload.get("error") or "G2 gate-close rejected: g2 topology report check failed")


def _validate_g3_close(out_dir: Path) -> None:
    cov_result = _run_section_ctl(out_dir, "check-coverage")
    if not cov_result.get("ok"):
        errors = cov_result.get("errors") or [cov_result.get("error", "coverage check failed")]
        _fail("G3 coverage predicate not met: " + "; ".join(str(e) for e in errors))


def _validate_g4_close(out_dir: Path) -> dict[str, Any]:
    """Merge structural (recompose-check) + semantic (g4-recompose-report) predicates.

    Structural (reforms_shape / shape_absorbed) come from
    inductive_g3_section_control.py recompose-check (mechanical, script-checkable).
    Semantic (conflicts / buildable / reversible / verifiable) come from the
    g4-recompose-runner subagent's report, read via inductive_g4_control.py
    list-recompose-report. Neither is supplied by the caller — G4 cannot be
    closed by an AI-recalled payload.
    """
    # Structural predicates first (mirrors SKILL step 1 -> step 2 ordering) — a
    # structural failure should surface as itself, not be masked by "report
    # missing" when the semantic half was never even dispatched yet.
    struct = _run_section_ctl(out_dir, "recompose-check")
    recompose = struct.get("recompose_check") or {}
    if not recompose:
        _fail(struct.get("error") or "recompose-check failed to return recompose_check")

    struct_errors = recompose.get("errors") or []
    struct_detail = f" ({'; '.join(struct_errors)})" if struct_errors else ""

    if not recompose.get("reforms_shape"):
        _fail(f"G4 gate-close rejected: reforms_shape=false; reopen G1 to correct shape{struct_detail}")

    if not recompose.get("shape_absorbed"):
        _fail(f"G4 gate-close rejected: shape_absorbed=false; rewind affected sections{struct_detail}")

    cmd = _g4_ctl(out_dir) + ["list-recompose-report"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        semantic = json.loads(result.stdout)
    except json.JSONDecodeError:
        _fail(result.stdout or result.stderr or "list-recompose-report failed")
    if result.returncode != 0 or not semantic.get("ok"):
        _fail(
            semantic.get("error")
            or "g4 recompose report unreadable; dispatch g4-recompose-runner first"
        )

    merged = {
        "reforms_shape": recompose.get("reforms_shape"),
        "shape_absorbed": recompose.get("shape_absorbed"),
        "conflicts": semantic.get("conflicts", []),
        "buildable": semantic.get("buildable"),
        "reversible": semantic.get("reversible"),
        "verifiable": semantic.get("verifiable"),
    }

    conflicts = merged["conflicts"] or []
    if conflicts:
        _fail(
            f"G4 gate-close rejected: {len(conflicts)} conflict(s) unresolved; "
            "rewind affected sections to resolve"
        )

    for field in ("buildable", "reversible", "verifiable"):
        if not merged.get(field):
            _fail(f"G4 gate-close rejected: {field}=false")

    return merged


# ---------------------------------------------------------------------------
# DQI I/O
# ---------------------------------------------------------------------------

def _write_dqi_field(out_dir: Path, field: str, value: Any) -> None:
    """Merge a field into inductive-dqi.json (create if missing)."""
    dqi_p = _dqi_path(out_dir)
    if dqi_p.exists():
        try:
            dqi = json.loads(dqi_p.read_text(encoding="utf-8"))
        except Exception:
            dqi = {}
    else:
        dqi = {"version": "1"}

    dqi[field] = value

    dqi_p.parent.mkdir(parents=True, exist_ok=True)
    with dqi_p.open("w", encoding="utf-8") as fh:
        json.dump(dqi, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def cmd_gate_reopen(out_dir: Path, args: argparse.Namespace) -> None:
    """Reopen a gate that was previously closed (e.g. G4 audit failure → reopen G3).

    Sets the target gate to 'reopened' and resets all downstream gates to 'pending'.
    The active_gate is moved back to the target gate so gate-close can be called
    again after the issue is resolved.

    --sections (G3 only) atomically pairs the reopen with rewind-section for each
    listed section, so the caller can never leave the spine half-paired (gate
    reopened but the affected section still 'cleared').
    """
    gate: str = args.gate.upper()
    sections_arg = (getattr(args, "sections", "") or "").strip()
    if sections_arg and gate != "G3":
        _fail("--sections is only valid with --gate G3 (pairs reopen with rewind-section)")
    if gate not in GATE_ORDER:
        _fail(f"invalid gate: {gate!r}; must be one of {GATE_ORDER}")

    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)
    current_active = state.get("active_gate", "")

    target_idx = GATE_ORDER.index(gate)
    active_idx = GATE_ORDER.index(current_active) if current_active in GATE_ORDER else -1

    # Can only reopen a gate that has been reached (active_gate >= target)
    if active_idx < target_idx:
        _fail(
            f"cannot reopen gate {gate!r}: it has not been reached yet "
            f"(active_gate={current_active!r})"
        )

    # No-op if the gate is already open/active/reopened
    if active_idx == target_idx and not is_gate_closed(state, gate):
        _fail(
            f"gate {gate!r} is already active or reopened — nothing to reopen"
        )

    updated = reopen_gate(state, gate)
    save_gate_state(gate_path, updated)

    deleted_g2_report = False
    if gate == "G1":
        cmd = _g2_ctl(out_dir) + ["delete-g2-report"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            _fail(result.stdout or result.stderr or "delete-g2-report failed")
        if result.returncode != 0 or not payload.get("ok"):
            _fail(payload.get("error") or "delete-g2-report failed")
        deleted_g2_report = bool(payload.get("deleted"))

    # G4's semantic report is downstream of both G1 and G3 — a stale report must
    # not be readable as if it still reflects the post-fix state.
    deleted_g4_report = False
    if gate in ("G1", "G3"):
        cmd = _g4_ctl(out_dir) + ["delete-recompose-report"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            _fail(result.stdout or result.stderr or "delete-recompose-report failed")
        if result.returncode != 0 or not payload.get("ok"):
            _fail(payload.get("error") or "delete-recompose-report failed")
        deleted_g4_report = bool(payload.get("deleted"))

    rewound_sections: list[str] = []
    if sections_arg:
        for section in [s.strip().upper() for s in sections_arg.split(",") if s.strip()]:
            result = _run_section_ctl(out_dir, "rewind-section", "--to", section)
            if not result.get("ok"):
                _fail(f"rewind-section failed for {section!r}: " + result.get("error", "unknown"))
            rewound_sections.append(section)

    _ok({
        "reopened": gate,
        "active_gate": updated["active_gate"],
        "deleted_g2_report": deleted_g2_report,
        "deleted_g4_report": deleted_g4_report,
        "rewound_sections": rewound_sections,
        "note": (
            "downstream gates reset to pending; "
            "resolve the issue then call gate-close again"
        ),
    })


def cmd_g2_check_report(out_dir: Path, _args: argparse.Namespace) -> None:
    _forward_ctl(_g2_ctl(out_dir), "check-g2-report")


def cmd_g2_list_report(out_dir: Path, _args: argparse.Namespace) -> None:
    _forward_ctl(_g2_ctl(out_dir), "list-g2-report")


def cmd_g4_check_report(out_dir: Path, _args: argparse.Namespace) -> None:
    _forward_ctl(_g4_ctl(out_dir), "check-recompose-report")


def cmd_g4_list_report(out_dir: Path, _args: argparse.Namespace) -> None:
    _forward_ctl(_g4_ctl(out_dir), "list-recompose-report")


def cmd_grounding_check(out_dir: Path, args: argparse.Namespace) -> None:
    if args.sweep is None:
        _fail("--sweep is required")
    _forward_ctl(
        _g3_grounding_ctl(out_dir),
        "check-grounding",
        "--sweep",
        str(args.sweep),
    )


def cmd_grounding_list(out_dir: Path, args: argparse.Namespace) -> None:
    if args.sweep is None:
        _fail("--sweep is required")
    _forward_ctl(
        _g3_grounding_ctl(out_dir),
        "list-grounding",
        "--sweep",
        str(args.sweep),
    )


def cmd_deep_grounding_list(out_dir: Path, args: argparse.Namespace) -> None:
    if args.sweep is None:
        _fail("--sweep is required")
    if not args.ep_id:
        _fail("--ep-id is required")
    _forward_ctl(
        _g3_grounding_ctl(out_dir),
        "list-grounding",
        "--sweep",
        str(args.sweep),
        "--mode",
        "deep",
        "--ep-id",
        args.ep_id,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    # hook_guard appends --conversation-id after the subcommand and its args.
    conv_id_parent = argparse.ArgumentParser(add_help=False)
    conv_id_parent.add_argument(
        "--conversation-id",
        default="",
        help="Injected by hook_guard; platform session identity (omit from agent templates).",
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[conv_id_parent],
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        metavar="PATH",
        help="$INDUCTIVE_OUT_DIR: directory for inductive state files and artifacts",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # init-session
    p = sub.add_parser(
        "init-session",
        help="Seed gate state + section pointer",
        parents=[conv_id_parent],
    )
    p.add_argument("--sections", required=True, help="Comma-separated coverage_sections")
    p.add_argument("--mandatory", default="", help="Comma-separated mandatory section keys")
    p.add_argument("--cycle-id", default="", help="Cycle id for traceability")
    p.add_argument("--stage", default="", help="Compose stage id (e.g. lulu-design)")

    # resolve-context
    sub.add_parser(
        "resolve-context",
        help="Return active_gate, active_section, open-EP count (multi-turn resume entry)",
        parents=[conv_id_parent],
    )

    # gate-close
    p = sub.add_parser(
        "gate-close",
        help="Close a gate with payload validation",
        parents=[conv_id_parent],
    )
    p.add_argument("--gate", required=True, metavar="G", help="G1 | G2 | G3 | G4")
    p.add_argument(
        "--payload",
        default="{}",
        metavar="JSON",
        help="Gate-specific close payload (JSON object)",
    )

    # gate-reopen
    p = sub.add_parser(
        "gate-reopen",
        help="Reopen a previously closed gate (e.g. G4 audit failure → reopen G3)",
        parents=[conv_id_parent],
    )
    p.add_argument(
        "--gate",
        required=True,
        metavar="G",
        help="G1 | G2 | G3 | G4 — gate to reopen; downstream gates reset to pending",
    )
    p.add_argument(
        "--sections",
        default="",
        help="Comma-separated section keys to rewind (only valid with --gate G3); "
             "atomically pairs gate-reopen with rewind-section",
    )

    sub.add_parser(
        "g2-check-report",
        help="Validate g2-topology-report (facade)",
        parents=[conv_id_parent],
    )
    sub.add_parser(
        "g2-list-report",
        help="Read g2-topology-report summary (facade)",
        parents=[conv_id_parent],
    )

    p = sub.add_parser(
        "grounding-check",
        help="Validate sweep grounding receipts (facade)",
        parents=[conv_id_parent],
    )
    p.add_argument("--sweep", type=int, required=True)

    p = sub.add_parser(
        "grounding-list",
        help="List sweep grounding receipts (facade)",
        parents=[conv_id_parent],
    )
    p.add_argument("--sweep", type=int, required=True)

    p = sub.add_parser(
        "deep-grounding-list",
        help="List the deep grounding receipt for one open point (facade)",
        parents=[conv_id_parent],
    )
    p.add_argument("--sweep", type=int, required=True)
    p.add_argument("--ep-id", required=True)

    sub.add_parser(
        "g4-check-report",
        help="Validate g4-recompose-report (facade)",
        parents=[conv_id_parent],
    )
    sub.add_parser(
        "g4-list-report",
        help="Read g4-recompose-report summary (facade)",
        parents=[conv_id_parent],
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "init-session": cmd_init_session,
        "resolve-context": cmd_resolve_context,
        "gate-close": cmd_gate_close,
        "gate-reopen": cmd_gate_reopen,
        "g2-check-report": cmd_g2_check_report,
        "g2-list-report": cmd_g2_list_report,
        "grounding-check": cmd_grounding_check,
        "grounding-list": cmd_grounding_list,
        "deep-grounding-list": cmd_deep_grounding_list,
        "g4-check-report": cmd_g4_check_report,
        "g4-list-report": cmd_g4_list_report,
    }

    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")

    handler(out_dir, args)


if __name__ == "__main__":
    main()

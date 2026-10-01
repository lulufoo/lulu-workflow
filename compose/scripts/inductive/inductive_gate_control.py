#!/usr/bin/env python3
"""Inductive runner outer gate spine control.

Manages the G2->G3->G4 lock machine. After G4 closes, active_gate
becomes complete. Provenance audit is delivery Eval, not a G5 gate.

Subcommands:
    init-session        Seed gate state only
    resolve-context     Return active_gate, gates, open_point (idle zeros
                        when Open-point files are absent), and
                        guide (Domain cognitive_frame + intent_anchor).
                        Fails if --project-root or gate-state.stage is
                        missing, or the Domain instance cannot be loaded.
    gate-close          Close a gate with payload / mode validation
    gate-reopen         Reopen a gate; downstream gates reset to pending
                        (also deletes the stale g4 report where applicable).
                        G3 reopen requires --from-report --report-digest.
    g4-check-report     Facade: subprocess to inductive_recompose_control check-recompose-report
    g4-list-report      Facade: subprocess to inductive_recompose_control list-recompose-report
    record-topic-landscape  Persist single-slot _topic-landscape.json (new run_id)
    record-g2-topic-exit    Persist _g2-topic-exit.json referencing a landscape run_id

Close per gate:
    G2: Topic Loop exit — topic_loop_done + design_goal_met + human_exit_confirmed
        + topic_exit in {cleared, hard_skip} matching _g2-topic-exit.json /
          pre_close _topic-landscape.json (archive-21)
    G3: --mode cleared|hard-skip --confirm; lock + open_point_store.check_close
    G4: report-driven; --payload ignored; empty findings + three true predicates
        + matching facts/opens digests
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

_COMPOSE_SCRIPTS = Path(__file__).resolve().parents[1]
_OPEN_POINT = _HERE / "open-point"
_RECOMPOSE = _HERE / "recompose"
_SESSION = _COMPOSE_SCRIPTS / "schema" / "session"
_KERNEL = _COMPOSE_SCRIPTS / "_kernel"
_SCOPE = _COMPOSE_SCRIPTS / "schema" / "section" / "scope"
_SCHEMA_DIRS = (
    _HERE / "schema" / "gate",
    _HERE / "schema" / "topic",
    _HERE / "schema" / "open-point",
    _HERE / "schema" / "recompose",
)
for _p in (_COMPOSE_SCRIPTS, _OPEN_POINT, _SESSION, _KERNEL, *_SCHEMA_DIRS, _SCOPE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from active_context_schema import resolve_conversation_id  # noqa: E402
from compose_state_lock import canonical_digest, compose_state_lock  # noqa: E402
from recompose_report_schema import (  # noqa: E402
    delete_report,
    recompose_report_path,
    load_report,
    validate_finding_lens_sources,
)
from execution_state_schema import working_execution_dir  # noqa: E402
from open_point_state_schema import (  # noqa: E402
    empty_open_point_state,
    load_open_point_state,
    open_point_state_path,
)
from open_point_store import (  # noqa: E402
    OpenPointError,
    abandon_active_batch,
    apply_targets,
    assert_slice_writable,
    check_close,
    facts_digest,
    facts_snapshot,
    prepare_add_opens,
)
from opens_schema import load_opens, opens_path  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from domain_instance_schema import load_and_validate_domain_instance  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402

from inductive_gate_state_schema import (  # noqa: E402
    GATE_ORDER,
    close_gate,
    header_gate_symbols,
    init_gate_state,
    is_gate_closed,
    load_gate_state,
    reopen_gate,
    routing_index,
    save_gate_state,
)
from topic_exit_schema import (  # noqa: E402
    topic_exit_path,
    load_topic_exit,
    save_topic_exit,
)
from topic_landscape_schema import (  # noqa: E402
    LANDSCAPE_PURPOSES,
    load_topic_landscape,
    new_run_id,
    save_topic_landscape,
    topic_landscape_path,
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


def _g4_ctl(out_dir: Path) -> list[str]:
    script = _RECOMPOSE / "inductive_recompose_control.py"
    return [sys.executable, str(script), "--out-dir", str(out_dir)]


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
    stage = str(args.stage or "").strip()
    root = str(getattr(args, "project_root", "") or "").strip()
    if root:
        try:
            stage = resolve_revision_runtime_profile(
                out_dir,
                Path(root).resolve(),
                cycle_id=cycle_id.strip() or None,
            ).profile_id
        except (OSError, ValueError, FileNotFoundError):
            pass
    state = init_gate_state(
        cycle_id=cycle_id,
        stage=stage,
        master_conversation_id=master_conv,
    )
    save_gate_state(gate_path, state)

    _ok({
        "message": "session initialized",
        "active_gate": state["active_gate"],
    })


def _guide(state: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    """Load Domain D1/D2 for $CTX.guide. Fail closed."""
    root = str(getattr(args, "project_root", "") or "").strip()
    if not root:
        _fail("resolve-context failed: --project-root is required to load guide")
    stage = str(state.get("stage") or "").strip()
    if not stage:
        _fail(
            "resolve-context failed: gate-state.stage is empty; "
            "cannot resolve domain instance"
        )
    cycle_type = detect_cycle_type(str(state.get("cycle_id") or ""))
    try:
        domain = load_and_validate_domain_instance(
            cycle_type,
            project_root=Path(root).resolve(),
            profile_id=stage,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        _fail(f"guide unresolved: {exc}")
    return {
        "cognitive_frame": str(domain["cognitive_frame"]),
        "intent_anchor": str(domain["intent_anchor"]),
    }


def _open_point_view(slice_dir: Path) -> dict[str, Any]:
    idle = empty_open_point_state()
    try:
        opens = load_opens(opens_path(slice_dir))
        state = load_open_point_state(open_point_state_path(slice_dir))
    except (OSError, ValueError):
        return {
            "phase": idle["phase"],
            "active_batch_id": idle["active_batch_id"],
            "active_open_id": idle["active_open_id"],
            "open_count": 0,
        }
    return {
        "phase": state.get("phase", "idle"),
        "active_batch_id": state.get("active_batch_id"),
        "active_open_id": state.get("active_open_id"),
        "open_count": sum(1 for item in opens if item.get("status") == "open"),
    }


def cmd_resolve_context(out_dir: Path, args: argparse.Namespace) -> None:
    """Multi-turn resume entry point: aggregate gate + open-point + D1/D2."""
    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)
    symbols = header_gate_symbols(state)
    slice_dir = working_execution_dir(out_dir)
    open_point = _open_point_view(slice_dir)
    guide = _guide(state, args)

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
        "open_point": open_point,
        "architecture_view": architecture_view,
        "guide": guide,
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

    payload: dict[str, Any] = {}
    if gate == "G2":
        if args.payload:
            try:
                payload = json.loads(args.payload)
            except json.JSONDecodeError as exc:
                _fail(f"invalid payload JSON: {exc}")
        _validate_g2_close(out_dir, payload)
        updated = close_gate(state, gate, payload=payload if payload else None)
        save_gate_state(gate_path, updated)
    elif gate == "G3":
        slice_dir = working_execution_dir(out_dir)
        with compose_state_lock(slice_dir):
            try:
                assert_slice_writable(slice_dir)
            except OpenPointError as exc:
                _fail(str(exc))
            payload = _validate_g3_close(slice_dir, args)
            updated = close_gate(state, gate, payload=payload)
            save_gate_state(gate_path, updated)
    elif gate == "G4":
        slice_dir = working_execution_dir(out_dir)
        with compose_state_lock(slice_dir):
            payload = _validate_g4_close(slice_dir)
            updated = close_gate(state, gate, payload=payload)
            save_gate_state(gate_path, updated)
    else:
        _fail(f"invalid gate: {gate!r}")

    _ok({
        "closed": gate,
        "active_gate": updated["active_gate"],
    })


# ---------------------------------------------------------------------------
# Gate-specific payload validators
# ---------------------------------------------------------------------------

def _validate_g2_close(out_dir: Path, payload: dict[str, Any]) -> None:
    """G2 = Topic Loop. Design-convergence exit.

    Requires ``topic_loop_done``, ``design_goal_met`` (AI D1+D2 gate),
    ``human_exit_confirmed``, ``topic_exit`` in ``{cleared, hard_skip}``, and a
    matching pre_close landscape + exit receipt pair (archive-21). Does **not**
    require a process draft / draft-as-topic-tree. Blocks when
    ``_topic-current.json`` has an unconfirmed conclusion.
    """
    if not payload.get("topic_loop_done"):
        _fail("G2 payload must include 'topic_loop_done': true (Topic Loop exit)")
    if not payload.get("design_goal_met"):
        _fail(
            "G2 payload must include 'design_goal_met': true "
            "(AI D1+D2 design-goal check passed)",
        )
    if not payload.get("human_exit_confirmed"):
        _fail(
            "G2 payload must include 'human_exit_confirmed': true "
            "(human confirmed exit after design_goal_met)",
        )
    topic_exit = payload.get("topic_exit")
    if topic_exit not in ("cleared", "hard_skip"):
        _fail(
            "G2 payload must include 'topic_exit' in "
            "{'cleared', 'hard_skip'} "
            "(pre-close topic-landscape: no gap-state topics, or human hard-skip)",
        )

    slice_dir = working_execution_dir(Path(out_dir))
    try:
        landscape = load_topic_landscape(topic_landscape_path(slice_dir))
        exit_receipt = load_topic_exit(topic_exit_path(slice_dir))
    except ValueError as exc:
        _fail(f"G2 close blocked: invalid landscape/exit receipt: {exc}")

    if exit_receipt is None:
        _fail(
            "G2 close blocked: missing _g2-topic-exit.json "
            "(run record-g2-topic-exit after pre-close topic-landscape)",
        )
    if landscape is None:
        _fail(
            "G2 close blocked: missing _topic-landscape.json "
            "(run record-topic-landscape --purpose pre_close)",
        )
    if exit_receipt.get("human_confirmed") is not True:
        _fail("G2 close blocked: exit receipt human_confirmed must be true")
    if exit_receipt.get("result") != topic_exit:
        _fail(
            "G2 close blocked: payload.topic_exit "
            f"{topic_exit!r} != exit.result {exit_receipt.get('result')!r}",
        )
    if exit_receipt.get("landscape_run_id") != landscape.get("run_id"):
        _fail(
            "G2 close blocked: exit.landscape_run_id does not match "
            "current _topic-landscape.json run_id",
        )
    if landscape.get("purpose") != "pre_close":
        _fail(
            "G2 close blocked: landscape.purpose must be 'pre_close' "
            f"(got {landscape.get('purpose')!r})",
        )
    if exit_receipt.get("gap_remaining") != landscape.get("gap_remaining"):
        _fail(
            "G2 close blocked: exit.gap_remaining "
            f"{exit_receipt.get('gap_remaining')!r} != landscape.gap_remaining "
            f"{landscape.get('gap_remaining')!r}",
        )
    if topic_exit == "cleared" and int(landscape.get("gap_remaining") or 0) != 0:
        _fail(
            "G2 close blocked: topic_exit=cleared requires landscape.gap_remaining=0",
        )

    # Same path as $TOPIC_CURRENT_CTL (active slice when multi-L pointer exists)
    topic_path = slice_dir / "_topic-current.json"
    if topic_path.is_file():
        try:
            topic = json.loads(topic_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _fail(f"invalid _topic-current.json: {exc}")
        conclusion = topic.get("conclusion")
        if isinstance(conclusion, str) and conclusion.strip():
            if not topic.get("conclusion_confirmed"):
                _fail(
                    "G2 close blocked: topic conclusion present but not confirmed "
                    "(confirm-conclusion or clear topic first)",
                )


def cmd_record_topic_landscape(out_dir: Path, args: argparse.Namespace) -> None:
    purpose = str(args.purpose or "").strip()
    if purpose not in LANDSCAPE_PURPOSES:
        _fail(
            "record-topic-landscape --purpose must be one of "
            + ", ".join(sorted(LANDSCAPE_PURPOSES)),
        )
    gap = int(args.gap_remaining)
    if gap < 0:
        _fail("record-topic-landscape --gap-remaining must be >= 0")
    summary = args.summary
    slice_dir = working_execution_dir(Path(out_dir))
    path = topic_landscape_path(slice_dir)
    data = {
        "version": "1",
        "run_id": new_run_id(),
        "purpose": purpose,
        "gap_remaining": gap,
        "summary": None if summary is None else str(summary),
    }
    try:
        saved = save_topic_landscape(path, data)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"ok": True, "path": str(path), "landscape": saved})


def cmd_record_g2_topic_exit(out_dir: Path, args: argparse.Namespace) -> None:
    result = str(args.result or "").strip()
    if result not in ("cleared", "hard_skip"):
        _fail("record-g2-topic-exit --result must be cleared or hard_skip")
    if not bool(getattr(args, "human_confirmed", False)):
        _fail("record-g2-topic-exit requires --human-confirmed")

    slice_dir = working_execution_dir(Path(out_dir))
    land_path = topic_landscape_path(slice_dir)
    try:
        landscape = load_topic_landscape(land_path)
    except ValueError as exc:
        _fail(f"invalid _topic-landscape.json: {exc}")
    if landscape is None:
        _fail(
            "record-g2-topic-exit requires _topic-landscape.json "
            "(run record-topic-landscape --purpose pre_close first)",
        )

    run_id = str(getattr(args, "landscape_run_id", "") or "").strip()
    if not run_id:
        run_id = str(landscape.get("run_id") or "")
    if run_id != landscape.get("run_id"):
        _fail(
            "record-g2-topic-exit landscape_run_id does not match "
            "current _topic-landscape.json run_id",
        )
    if landscape.get("purpose") != "pre_close":
        _fail(
            "record-g2-topic-exit requires landscape.purpose=pre_close "
            f"(got {landscape.get('purpose')!r})",
        )

    gap = int(landscape.get("gap_remaining") or 0)
    if args.gap_remaining is not None:
        gap_arg = int(args.gap_remaining)
        if gap_arg != gap:
            _fail(
                "record-g2-topic-exit --gap-remaining must equal "
                f"landscape.gap_remaining ({gap})",
            )
        gap = gap_arg
    if result == "cleared" and gap != 0:
        _fail("record-g2-topic-exit result=cleared requires landscape.gap_remaining=0")

    path = topic_exit_path(slice_dir)
    data = {
        "version": "1",
        "landscape_run_id": run_id,
        "result": result,
        "gap_remaining": gap,
        "human_confirmed": True,
        "purpose": "pre_close",
    }
    try:
        saved = save_topic_exit(path, data)
    except ValueError as exc:
        _fail(str(exc))
    _ok({"ok": True, "path": str(path), "exit": saved, "landscape": landscape})


def _validate_g3_close(slice_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "") or "").strip()
    if mode not in ("cleared", "hard-skip"):
        _fail("G3 close requires --mode cleared|hard-skip")
    if not bool(getattr(args, "confirm", False)):
        _fail("G3 close requires --confirm")
    try:
        result = check_close(
            slice_dir,
            mode=mode,
            project_root=getattr(args, "project_root", "") or None,
        )
    except OpenPointError as exc:
        _fail(str(exc))
    if not result.get("ok"):
        reasons = result.get("reasons") or ["close check failed"]
        _fail("G3 close rejected: " + "; ".join(str(item) for item in reasons))
    if mode == "hard-skip":
        abandon_active_batch(slice_dir)
    return {"mode": mode}


def _validate_g4_close(slice_dir: Path) -> dict[str, Any]:
    path = recompose_report_path(slice_dir)
    if not path.exists():
        _fail("g4 recompose report missing; dispatch recompose-runner first")
    try:
        report = load_report(path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
    current_facts = facts_digest(slice_dir)
    current_opens = canonical_digest(load_opens(opens_path(slice_dir)))
    if (
        report.get("facts_digest") != current_facts
        or report.get("opens_digest") != current_opens
    ):
        _fail("G4 gate-close rejected: stale report digest")
    findings = report.get("findings") or []
    if findings:
        _fail(f"G4 gate-close rejected: {len(findings)} finding(s) remain")
    for field in ("buildable", "reversible", "verifiable"):
        if report.get(field) is not True:
            _fail(f"G4 gate-close rejected: {field}=false")
    return {
        "findings": [],
        "buildable": True,
        "reversible": True,
        "verifiable": True,
        "facts_digest": current_facts,
        "opens_digest": current_opens,
    }


def _reopen_g3_from_report(out_dir: Path, args: argparse.Namespace, state: dict[str, Any]) -> None:
    digest = str(getattr(args, "report_digest", "") or "").strip()
    if not digest:
        _fail("gate-reopen --gate G3 --from-report requires --report-digest")
    slice_dir = working_execution_dir(out_dir)
    with compose_state_lock(slice_dir):
        path = recompose_report_path(slice_dir)
        if not path.exists():
            _fail("g4 recompose report missing; cannot reopen G3 from report")
        try:
            report = load_report(path)
        except (FileNotFoundError, ValueError) as exc:
            _fail(str(exc))
        if canonical_digest(report) != digest:
            _fail("G3 reopen rejected: report-digest mismatch")
        current_facts = facts_digest(slice_dir)
        current_opens = canonical_digest(load_opens(opens_path(slice_dir)))
        if (
            report.get("facts_digest") != current_facts
            or report.get("opens_digest") != current_opens
        ):
            _fail("G3 reopen rejected: stale report digest")
        findings = report.get("findings") or []
        if not findings:
            _fail("G3 reopen rejected: report has no findings")
        source_errors = validate_finding_lens_sources(
            findings, facts_snapshot(slice_dir), load_opens(opens_path(slice_dir))
        )
        if source_errors:
            _fail("; ".join(source_errors))
        incoming = []
        for item in findings:
            if not isinstance(item, dict):
                _fail("G3 reopen rejected: finding must be an object")
            lens = str(item.get("lens", "")).strip()
            if not lens:
                _fail("G3 reopen rejected: finding.lens is required")
            incoming.append(
                {
                    "question": item["question"],
                    "basis": item["basis"],
                    "blocking": item["blocking"],
                    "lens": lens,
                    "source": {"actor": "ai", "means": "audit"},
                }
            )
        try:
            prepared = prepare_add_opens(
                slice_dir,
                opens=incoming,
                project_root=getattr(args, "project_root", "") or None,
            )
            updated = reopen_gate(state, "G3")
            files = dict(prepared["files"])
            files["inductive-gate-state.json"] = updated
            files["g4-recompose-report.json"] = None
            apply_targets(slice_dir, "g3-from-report", files)
        except OpenPointError as exc:
            _fail(str(exc))
        except ValueError as exc:
            _fail(str(exc))
        added = {
            "opens": prepared["opens"],
            "state": prepared["state"],
            "batch": prepared["batch"],
            "receipt": prepared["receipt"],
        }
        deleted = not recompose_report_path(slice_dir).exists()
    _ok({
        "reopened": "G3",
        "active_gate": updated["active_gate"],
        "deleted_g4_report": deleted,
        "opens": added.get("opens", []),
        "note": (
            "findings registered as opens; downstream gates reset to pending; "
            "resolve the issue then call gate-close again"
        ),
    })


def cmd_gate_reopen(out_dir: Path, args: argparse.Namespace) -> None:
    """Reopen a previously closed gate.

    G3 requires --from-report --report-digest and registers report findings.
    G2 is a spine reopen that deletes the stale G4 report.
    """
    gate: str = args.gate.upper()
    sections_arg = (getattr(args, "sections", "") or "").strip()
    if sections_arg:
        _fail("--sections is rejected; G3 reopen is --from-report only")
    if gate not in GATE_ORDER:
        _fail(f"invalid gate: {gate!r}; must be one of {GATE_ORDER}")

    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)
    current_active = state.get("active_gate", "")

    target_idx = GATE_ORDER.index(gate)
    active_idx = routing_index(str(current_active))

    if active_idx < target_idx:
        _fail(
            f"cannot reopen gate {gate!r}: it has not been reached yet "
            f"(active_gate={current_active!r})"
        )

    if active_idx == target_idx and not is_gate_closed(state, gate):
        _fail(
            f"gate {gate!r} is already active or reopened — nothing to reopen"
        )

    if gate == "G3":
        if not bool(getattr(args, "from_report", False)):
            _fail("gate-reopen --gate G3 requires --from-report --report-digest")
        _reopen_g3_from_report(out_dir, args, state)
        return

    updated = reopen_gate(state, gate)
    save_gate_state(gate_path, updated)

    deleted_g4_report = False
    if gate == "G2":
        deleted_g4_report = delete_report(working_execution_dir(out_dir))

    _ok({
        "reopened": gate,
        "active_gate": updated["active_gate"],
        "deleted_g4_report": deleted_g4_report,
        "note": (
            "downstream gates reset to pending; "
            "resolve the issue then call gate-close again"
        ),
    })


def cmd_g4_check_report(out_dir: Path, _args: argparse.Namespace) -> None:
    _forward_ctl(_g4_ctl(out_dir), "check-recompose-report")


def cmd_g4_list_report(out_dir: Path, _args: argparse.Namespace) -> None:
    _forward_ctl(_g4_ctl(out_dir), "list-recompose-report")


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
    parser.add_argument(
        "--project-root",
        default="",
        metavar="PATH",
        help=(
            "Project root: init-session fills gate-state.stage from the revision "
            "pointer; resolve-context loads guide from the Domain instance"
        ),
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # init-session
    p = sub.add_parser(
        "init-session",
        help="Seed gate state",
        parents=[conv_id_parent],
    )
    p.add_argument("--cycle-id", default="", help="Cycle id for traceability")
    p.add_argument(
        "--stage",
        default="",
        help="Optional compose stage id when no revision pointer is available",
    )

    # resolve-context
    sub.add_parser(
        "resolve-context",
        help="Return active_gate, gates, open_point, and guide",
        parents=[conv_id_parent],
    )

    # gate-close
    p = sub.add_parser(
        "gate-close",
        help="Close a gate with payload / mode validation",
        parents=[conv_id_parent],
    )
    p.add_argument("--gate", required=True, metavar="G", help="G2 | G3 | G4")
    p.add_argument(
        "--payload",
        default="{}",
        metavar="JSON",
        help="G2 close payload (JSON object); ignored for G4",
    )
    p.add_argument(
        "--mode",
        default="",
        help="G3 only: cleared | hard-skip",
    )
    p.add_argument(
        "--confirm",
        action="store_true",
        help="G3 only: required human confirm",
    )

    # gate-reopen
    p = sub.add_parser(
        "gate-reopen",
        help="Reopen a previously closed gate (G3 requires --from-report)",
        parents=[conv_id_parent],
    )
    p.add_argument(
        "--gate",
        required=True,
        metavar="G",
        help="G2 | G3 | G4 — gate to reopen; downstream gates reset to pending",
    )
    p.add_argument(
        "--sections",
        default="",
        help="Rejected; G3 reopen is --from-report only",
    )
    p.add_argument(
        "--from-report",
        action="store_true",
        dest="from_report",
        help="G3 only: register findings from the current G4 report",
    )
    p.add_argument(
        "--report-digest",
        default="",
        dest="report_digest",
        help="G3 --from-report: canonical digest of the G4 report",
    )

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

    p = sub.add_parser(
        "record-topic-landscape",
        help="Persist single-slot _topic-landscape.json with a new run_id",
        parents=[conv_id_parent],
    )
    p.add_argument(
        "--purpose",
        required=True,
        choices=sorted(LANDSCAPE_PURPOSES),
        help="seek | refresh | pre_close",
    )
    p.add_argument(
        "--gap-remaining",
        required=True,
        type=int,
        help="Caller-reported count of gap-state topics after this landscape run",
    )
    p.add_argument("--summary", default=None, help="Optional short reuse summary")

    p = sub.add_parser(
        "record-g2-topic-exit",
        help="Persist _g2-topic-exit.json referencing current pre_close landscape",
        parents=[conv_id_parent],
    )
    p.add_argument(
        "--result",
        required=True,
        choices=["cleared", "hard_skip"],
        help="Human exit choice after pre-close landscape",
    )
    p.add_argument(
        "--human-confirmed",
        action="store_true",
        help="Required; records explicit human confirm of the exit choice",
    )
    p.add_argument(
        "--landscape-run-id",
        default="",
        help="Defaults to current _topic-landscape.json run_id",
    )
    p.add_argument(
        "--gap-remaining",
        type=int,
        default=None,
        help="Optional; must equal landscape.gap_remaining when set",
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
        "g4-check-report": cmd_g4_check_report,
        "g4-list-report": cmd_g4_list_report,
        "record-topic-landscape": cmd_record_topic_landscape,
        "record-g2-topic-exit": cmd_record_g2_topic_exit,
    }

    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")

    handler(out_dir, args)


if __name__ == "__main__":
    main()

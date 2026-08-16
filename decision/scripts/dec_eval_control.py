#!/usr/bin/env python3
"""Decision Eval control — bind target, summarize issues, pass/fail exit.

CLI:
    python3 dec_eval_control.py --project-root . --cycle-id <id> render-eval-target
    python3 dec_eval_control.py --project-root . --cycle-id <id> pass-exit
    python3 dec_eval_control.py --project-root . --cycle-id <id> fail-exit --issues-json '<array>'
    python3 dec_eval_control.py --project-root . --cycle-id <id> route-probe-result --probe-result-json '<object>'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_EVAL_ADAPTER = _SCRIPTS / "eval"
for p in (_SCRIPTS, _EVAL_ADAPTER):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from decision_eval_adapter import DecisionEvalAdapter  # noqa: E402
from dec_domain_constraints_schema import resolve_stage  # noqa: E402
from dec_eval_target_schema import render_and_save_eval_target  # noqa: E402
from dec_gate_state_schema import (  # noqa: E402
    is_gate_closed,
    is_gate_reached,
    load_gate_state,
)
from dec_session_paths import find_session_dir, session_artifact_paths  # noqa: E402
from dec_workflow_common import CACHE_DIR  # noqa: E402

# Single-dimension Eval: realign_gate must come from each issue (E/D/X per check).
REALIGN_BY_DIM: dict[str, str] = {}
_GATE_ORDER = ("O", "Q", "GL", "E", "D", "X", "R", "DC")


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _emit_error(message: str) -> int:
    return _emit({"ok": False, "error": message})


def _session_paths(project_root: Path, cycle_id: str, stage: str) -> dict[str, Path]:
    found = find_session_dir(project_root, cycle_id, stage, CACHE_DIR)
    if found is None:
        adapter = DecisionEvalAdapter()
        found = adapter._session_dir(cycle_id, project_root)
    return session_artifact_paths(found)


def cmd_render_eval_target(
    project_root: Path, cycle_id: str, stage: str
) -> int:
    try:
        paths = _session_paths(project_root, cycle_id, stage)
        constraints = json.loads(
            paths["domain_constraints"].read_text(encoding="utf-8")
        )
        from dec_domain_constraints_schema import (  # noqa: WPS433
            normalize_domain_constraints,
        )

        constraints = normalize_domain_constraints(constraints)
        gate_state = load_gate_state(paths["gate_state"])
        out = render_and_save_eval_target(
            paths["session_dir"],
            cycle_id=cycle_id,
            stage=str(constraints.get("stage") or stage),
            constraints=constraints,
            r_gate_closed=is_gate_closed(gate_state, "R"),
            r_risk_fields_allowed=is_gate_reached(gate_state, "R"),
        )
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    return _emit({"ok": True, "eval_target_path": out.as_posix()})


def _earliest_realign_gate(issues: list[dict[str, Any]]) -> str | None:
    gates: list[str] = []
    for issue in issues:
        gate = str(issue.get("realign_gate") or "").strip()
        if not gate:
            dim = str(issue.get("dimension_id") or issue.get("dim") or "").strip()
            gate = REALIGN_BY_DIM.get(dim, "")
        if gate:
            gates.append(gate)
    if not gates:
        return None
    return min(gates, key=lambda g: _GATE_ORDER.index(g) if g in _GATE_ORDER else 999)


def cmd_pass_exit(project_root: Path, cycle_id: str, stage: str) -> int:
    del stage
    adapter = DecisionEvalAdapter()
    try:
        result = adapter.finalize_eval_outcome(
            cycle_id, project_root, outcome="pass", issues=[]
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _emit_error(str(exc))
    return _emit(result)


def cmd_fail_exit(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    issues: list[dict[str, Any]],
) -> int:
    del stage
    enriched: list[dict[str, Any]] = []
    for issue in issues:
        item = dict(issue)
        dim = str(item.get("dimension_id") or item.get("dim") or "").strip()
        if not item.get("realign_gate") and dim in REALIGN_BY_DIM:
            item["realign_gate"] = REALIGN_BY_DIM[dim]
        enriched.append(item)
    adapter = DecisionEvalAdapter()
    try:
        result = adapter.finalize_eval_outcome(
            cycle_id, project_root, outcome="fail", issues=enriched
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _emit_error(str(exc))
    result["realign_gate"] = _earliest_realign_gate(enriched)
    result["disposition"] = "rs"
    return _emit(result)


def cmd_route_probe_result(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    probe_result: dict[str, Any],
) -> int:
    """Route Eval's completed Probe result through Decision's exit machine."""
    if (
        probe_result.get("ok") is not True
        or probe_result.get("command") != "complete-probe-only"
    ):
        return _emit_error("probe result must be a successful complete-probe-only payload")
    issues = probe_result.get("issues")
    if not isinstance(issues, list) or any(not isinstance(issue, dict) for issue in issues):
        return _emit_error("probe result issues must be an array of objects")
    if not issues:
        return cmd_pass_exit(project_root, cycle_id, stage)
    return cmd_fail_exit(
        project_root,
        cycle_id,
        stage,
        issues=[dict(issue) for issue in issues],
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decision Eval control.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--constraints", default="")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render-eval-target")
    sub.add_parser("pass-exit")
    fail = sub.add_parser("fail-exit")
    fail.add_argument(
        "--issues-json",
        default="[]",
        help="JSON array of issue objects (dimension_id, location, description, ...)",
    )
    route = sub.add_parser("route-probe-result")
    route.add_argument(
        "--probe-result-json",
        required=True,
        help="Successful complete-probe-only JSON emitted by Eval control",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    constraints_raw = str(args.constraints or "").strip()
    constraints_path = Path(constraints_raw).expanduser().resolve() if constraints_raw else None
    try:
        stage = resolve_stage(constraints_path)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    if args.command == "render-eval-target":
        return cmd_render_eval_target(project_root, cycle_id, stage)
    if args.command == "pass-exit":
        return cmd_pass_exit(project_root, cycle_id, stage)
    if args.command == "fail-exit":
        try:
            issues = json.loads(args.issues_json)
        except json.JSONDecodeError as exc:
            return _emit_error(f"invalid --issues-json: {exc}")
        if not isinstance(issues, list):
            return _emit_error("--issues-json must be a JSON array")
        return cmd_fail_exit(
            project_root,
            cycle_id,
            stage,
            issues=[item for item in issues if isinstance(item, dict)],
        )
    if args.command == "route-probe-result":
        try:
            probe_result = json.loads(args.probe_result_json)
        except json.JSONDecodeError as exc:
            return _emit_error(f"invalid --probe-result-json: {exc}")
        if not isinstance(probe_result, dict):
            return _emit_error("--probe-result-json must be a JSON object")
        return cmd_route_probe_result(
            project_root,
            cycle_id,
            stage,
            probe_result=probe_result,
        )
    return _emit_error(f"unknown command: {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())

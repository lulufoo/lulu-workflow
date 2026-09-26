#!/usr/bin/env python3
"""CLI for kernel Step 3 (derive) mechanical shell (K1).

Subcommands:
    edge-scan  Edge-coverage holes + topo order + true gaps (deductive-runner)
    audit      Cascade-aware self-audit after derived facts are appended
    append     Append derived facts (contiguous ids) and write ``_facts.json``
    classify   Classify zero-coverage required lenses (derivation vs true gap)

Design rationale (source repo, why-only): docs/ssot/compose/mechanism-ssot/compose-fact-architecture.md (Pd);
process how archive: docs/archive/lulu-dev-workflow/compose/archive-2.0/compose-fact-first-k1-pd-design.md §2/§5.
Scripts never invent derived work-item text — only mechanical shell.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_DERIVE = Path(__file__).resolve().parent
_SCRIPTS = _DERIVE.parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from execution_state_schema import execution_dir  # noqa: E402
from facts_schema import (  # noqa: E402
    facts_path,
    filter_by_lens,
    load_facts,
    pd_material_facts,
    save_facts,
)
from compose_state_lock import compose_state_lock  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402
from derive_shell import (  # noqa: E402
    DeriveCycleError,
    append_derived_facts,
    check_derive_nonempty_self_audit,
    classify_zero_required_lenses,
    derivation_upstreams,
    derive_triggers,
    edge_hole_triggers,
    normalize_dependency_graph,
    topo_order_triggered,
    true_coverage_gaps,
    upstream_fact_count,
)
from section_registry_schema import (  # noqa: E402
    dependency_graph_subset,
    fetch_section_registry,
    lens_key_sequence,
)

_INTAKE_EVAL_SCRIPTS = (
    _SCRIPTS.parent / "fact-intake-runner" / "fact-intake-eval" / "scripts"
)
_EVAL_SCRIPTS = _SCRIPTS.parents[1] / "eval" / "scripts"
for _p in (_INTAKE_EVAL_SCRIPTS, _EVAL_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()
from fact_intake_eval_runtime_schema import (  # noqa: E402
    evaluate_state_path as intake_evaluate_state_path,
    fact_intake_eval_root,
    gate_allows_derive_from_evaluate_state,
)
from evaluate_state_schema import load_evaluate_state  # noqa: E402


def _require_fact_intake_eval_for_derive(slice_dir: Path) -> str | None:
    """Return error message if intake eval gate blocks Derive; else None.

    Prefers ``{slice}/fact-intake-eval/``; falls back to legacy ``atomize-eval/``.
    """
    path = intake_evaluate_state_path(slice_dir)
    legacy = slice_dir.resolve() / "atomize-eval" / "evaluate-state.md"
    if not path.is_file() and legacy.is_file():
        path = legacy
    if not path.is_file():
        expected = fact_intake_eval_root(slice_dir) / "evaluate-state.md"
        return (
            "fact-intake eval gate missing — run Fact Intake Eval "
            f"(expected {expected.as_posix()})"
        )
    try:
        data = load_evaluate_state(path)
    except (OSError, ValueError) as exc:
        return f"fact-intake eval gate unreadable: {exc}"
    if not gate_allows_derive_from_evaluate_state(data):
        return (
            f"fact-intake eval gate not open (eval_status={data.get('eval_status')!r}); "
            "Derive blocked until Intake Eval remediation-complete (eval_status=done)"
        )
    return None


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _runtime_profile(args: argparse.Namespace):
    return resolve_revision_runtime_profile(
        Path(args.revision_dir),
        Path(args.project_root).resolve(),
    )


def _load_registry(
    project_root: Path,
    profile_id: str,
    *,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    return fetch_section_registry(
        project_root,
        profile_id=profile_id,
        profile_path=profile_path,
    )


def _graph_and_maps(
    project_root: Path,
    profile_id: str,
    *,
    profile_path: Path | None = None,
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    registry = _load_registry(
        project_root,
        profile_id,
        profile_path=profile_path,
    )
    graph = normalize_dependency_graph(dependency_graph_subset(registry))
    section_order = lens_key_sequence(registry)
    presence_map = {
        str(k).upper(): str(
            (registry.get("sections") or {}).get(k, {}).get("presence", "required")
        ).strip().lower()
        for k in section_order
    }
    for key, val in list(presence_map.items()):
        if val not in ("required", "optional"):
            presence_map[key] = "required"
    return graph, section_order, presence_map


def cmd_edge_scan(args: argparse.Namespace) -> int:
    """Edge-coverage scan for deductive-runner (holes + topo + true gaps)."""
    revision_dir = execution_dir(args.revision_dir.resolve())
    gate_err = _require_fact_intake_eval_for_derive(revision_dir)
    if gate_err:
        return _fail(gate_err)
    try:
        facts = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return _fail(str(exc))
    # archive-6.0 §5.6: default Pd materials = carried (+ legacy no-disposition).
    materials = pd_material_facts(facts)
    try:
        runtime = _runtime_profile(args)
        graph, section_order, presence_map = _graph_and_maps(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"section-registry unavailable: {exc}")

    edge_holes = edge_hole_triggers(section_order, presence_map, materials, graph)
    triggered = list(edge_holes.keys())
    # Also include required zero-coverage derivation lenses (subset of holes).
    for lens in derive_triggers(section_order, presence_map, materials, graph):
        if lens not in edge_holes:
            triggered.append(lens)
            edge_holes[lens] = []
    try:
        order = topo_order_triggered(triggered, graph) if triggered else []
    except DeriveCycleError as exc:
        return _fail(str(exc))
    gaps = true_coverage_gaps(section_order, presence_map, materials, graph)
    upstreams = {
        lens: {
            "upstreams": derivation_upstreams(lens, graph),
            "upstream_fact_count": upstream_fact_count(materials, lens, graph),
            "upstream_facts": [
                item
                for u in derivation_upstreams(lens, graph)
                for item in filter_by_lens(materials, u)
            ],
            "edge_holes": edge_holes.get(lens, []),
        }
        for lens in order
    }
    return _ok(
        {
            "ok": True,
            "command": "edge-scan",
            "triggered": triggered,
            "order": order,
            "edge_holes": edge_holes,
            "true_gaps": gaps,
            "upstreams": upstreams,
            "facts_total": len(facts),
            "materials_total": len(materials),
        }
    )


def cmd_audit(args: argparse.Namespace) -> int:
    revision_dir = execution_dir(args.revision_dir.resolve())
    try:
        after = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return _fail(str(exc))
    try:
        before = json.loads(Path(args.before_file).read_text(encoding="utf-8"))
        if not isinstance(before, list):
            return _fail("--before-file must be a JSON array")
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"cannot read --before-file: {exc}")

    triggered = [str(t).strip().upper() for t in args.triggered.split(",") if t.strip()]
    if not triggered:
        # Empty plan.order — no lenses fired; audit is a no-op success.
        return _ok(
            {
                "ok": True,
                "command": "audit",
                "triggered": [],
                "facts_after": len(after),
                "skipped": "empty-triggered",
            }
        )

    try:
        runtime = _runtime_profile(args)
        graph, _order, _presence = _graph_and_maps(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"section-registry unavailable: {exc}")

    errors = check_derive_nonempty_self_audit(before, after, triggered, graph)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    return _ok(
        {
            "ok": True,
            "command": "audit",
            "triggered": triggered,
            "facts_after": len(after),
        }
    )


def cmd_append(args: argparse.Namespace) -> int:
    revision_dir = execution_dir(args.revision_dir.resolve())
    try:
        base = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return _fail(str(exc))
    try:
        derived = json.loads(Path(args.derived_file).read_text(encoding="utf-8"))
        if not isinstance(derived, list):
            return _fail("--derived-file must be a JSON array")
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"cannot read --derived-file: {exc}")

    try:
        out = append_derived_facts(base, derived)
        runtime = _runtime_profile(args)
        registry = _load_registry(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
        allowed = lens_key_sequence(registry)
        save_facts(facts_path(revision_dir), out, allowed_lenses=allowed)
    except (ValueError, FileNotFoundError, OSError) as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "append",
            "facts_before": len(base),
            "facts_after": len(out),
            "appended": len(out) - len(base),
        }
    )


def cmd_classify(args: argparse.Namespace) -> int:
    revision_dir = execution_dir(args.revision_dir.resolve())
    try:
        facts = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return _fail(str(exc))
    try:
        runtime = _runtime_profile(args)
        graph, section_order, presence_map = _graph_and_maps(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"section-registry unavailable: {exc}")

    buckets = classify_zero_required_lenses(
        section_order, presence_map, facts, graph,
    )
    return _ok(
        {
            "ok": True,
            "command": "classify",
            "derivation": buckets["derivation"],
            "true_gaps": buckets["true_gaps"],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    edge_scan_p = sub.add_parser(
        "edge-scan",
        help="List edge-coverage holes in topo order + true gaps (deductive-runner)",
    )
    edge_scan_p.add_argument("--revision-dir", type=Path, required=True)
    edge_scan_p.add_argument("--project-root", type=Path, default=Path.cwd())
    edge_scan_p.set_defaults(func=cmd_edge_scan)

    audit_p = sub.add_parser("audit", help="Cascade-aware Step 3 self-audit")
    audit_p.add_argument("--revision-dir", type=Path, required=True)
    audit_p.add_argument(
        "--before-file",
        type=Path,
        required=True,
        help="Step 2 facts JSON snapshot taken before Step 3 append",
    )
    audit_p.add_argument(
        "--triggered",
        type=str,
        required=True,
        help="Comma-separated triggered lens keys (from edge-scan.order)",
    )
    audit_p.add_argument("--project-root", type=Path, default=Path.cwd())
    audit_p.set_defaults(func=cmd_audit)

    append_p = sub.add_parser("append", help="Append derived facts and write _facts.json")
    append_p.add_argument("--revision-dir", type=Path, required=True)
    append_p.add_argument("--derived-file", type=Path, required=True)
    append_p.add_argument("--project-root", type=Path, default=Path.cwd())
    append_p.set_defaults(func=cmd_append)

    classify_p = sub.add_parser(
        "classify",
        help="Classify zero-coverage required lenses (derivation vs true gap)",
    )
    classify_p.add_argument("--revision-dir", type=Path, required=True)
    classify_p.add_argument("--project-root", type=Path, default=Path.cwd())
    classify_p.set_defaults(func=cmd_classify)

    args = parser.parse_args()
    if args.command == "append":
        with compose_state_lock(execution_dir(args.revision_dir.resolve())):
            return args.func(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

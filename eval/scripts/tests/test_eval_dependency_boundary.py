"""Dependency-boundary tests for Eval production modules."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _EVAL_SCRIPTS.parents[1]
_FORBIDDEN_ROOTS = {"compose", "decision"}
_CUT_MODULE_NAMES = ("corpus_compose", "url_fetch", "evaluate_state_ops")
_CUT_EVAL_CONTROL_NAMES = (
    "_probe_result_issues",
    "_review_rows_for_dim",
    "collect_review_issues",
    "dimension_from_review_path",
    "build_dimensions",
    "build_issue_counts",
    "count_ignored",
    "compute_fix_severity",
    "_reason_from_issue",
    "_SEVERITY_RANK",
    "_review_prefix_from_corpus",
    "_publish_probe_review",
    "_abandoned_failure",
    "handling_mode_for_issue",
    "allowed_decisions_for_issue",
    "validate_review_against_probe_record",
    "canonical_probe_findings_from_reviews",
    "validate_review_completion",
    "_review_path_for_dim",
    "_review_path_from_context",
    "_load_corpus",
    "_evaluate_dir_for_snapshot",
    "_dispatch_dim_allowed",
    "dispatch_list",
    "_dispatch_canonical",
    "_paths_from_handoff",
    "_eval_paths",
    "_eval_dir",
    "_evaluate_state_path",
    "_bind_vars",
    "_expanded_corpus",
    "_canonical_dim",
    "_recompute_aggregate_counts",
    "_eval_capability",
    "_focus_phase",
    "_operations_path",
    "_dimension_def",
    "_operations_for_round",
    "_commit_staged_evaluate_state",
    "_load_evaluating_context",
    "validate_live_target_digest",
    "_content_digest",
    "_target_path_from_record",
    "_live_target_digest",
    "_review_live_state",
    "_target_live_state",
    "_render_review_after",
    "_publish_review_after",
    "_commit_eval_target",
    "_advance_phase",
    "_forward_recover_to_committed",
    "_load_probe_payload",
    "_render_probe_review",
    "prepare_remediation_at",
    "_remediation_command_context",
    "restore_eval_target",
)
_CUT_UNIT_VIEW_NAMES = (
    "main",
    "cmd_inspect",
    "prior_container_units",
    "severity_hints_chapter",
)
_ROOT_ONLY = {"eval_control.py", "eval_entry.py", "eval_path.py"}
_GRID = {
    "adapter": {
        "eval_adapter_config.py",
        "eval_handoff_schema.py",
        "workflow_adapter.py",
    },
    "admission": {"eval_admission.py"},
    "corpus": {
        "corpus_composition.py",
        "corpus_schema.py",
        "corpus_snapshot.py",
    },
    "operation": {
        "eval_operation_context.py",
        "eval_operation_record_schema.py",
    },
    "probe": {
        "codebase_sot.py",
        "eval_target_units.py",
        "probe_control.py",
        "remote_ref.py",
    },
    "remediation": {
        "operation_recovery.py",
        "remediation_control.py",
        "remediation_schema.py",
        "unified_diff.py",
    },
    "review": {"review_io.py", "review_schema.py", "review_binding.py"},
    "round": {
        "evaluate_context.py",
        "evaluate_state_binding.py",
        "evaluate_state_schema.py",
        "round_control.py",
        "session_binding.py",
    },
}


def _production_py() -> list[Path]:
    return [
        path
        for path in _EVAL_SCRIPTS.rglob("*.py")
        if "tests" not in path.relative_to(_EVAL_SCRIPTS).parts
    ]


def _stage_module_names() -> set[str]:
    names: set[str] = set()
    for stage in ("compose", "decision"):
        names.update(
            path.stem
            for path in (_WORKFLOW_ROOT / stage).rglob("*.py")
        )
    return names


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value.split(".", 1)[0])
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value.split(".", 1)[0])
    return names


def test_eval_production_modules_do_not_import_compose_or_decision() -> None:
    production = _production_py()
    stage_modules = (
        _stage_module_names()
        - {path.stem for path in production}
        | _FORBIDDEN_ROOTS
    )
    violations = {
        str(path.relative_to(_EVAL_SCRIPTS)): sorted(
            _imported_module_names(path) & stage_modules
        )
        for path in production
    }
    assert {
        name: modules for name, modules in violations.items() if modules
    } == {}


def test_eval_scripts_land_on_the_capability_grid() -> None:
    root_py = {path.name for path in _EVAL_SCRIPTS.glob("*.py")}
    assert root_py == _ROOT_ONLY
    for folder, names in _GRID.items():
        actual = {path.name for path in (_EVAL_SCRIPTS / folder).glob("*.py")}
        assert actual == names


def test_renamed_eval_modules_are_hard_cut() -> None:
    for name in _CUT_MODULE_NAMES:
        assert not (_EVAL_SCRIPTS / f"{name}.py").exists()
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_dead_eval_helpers_are_hard_cut() -> None:
    import eval_control
    import eval_target_units

    for name in _CUT_EVAL_CONTROL_NAMES:
        assert not hasattr(eval_control, name)
    for name in _CUT_UNIT_VIEW_NAMES:
        assert not hasattr(eval_target_units, name)
    source = Path(eval_target_units.__file__).read_text(encoding="utf-8")
    assert "--path" not in source

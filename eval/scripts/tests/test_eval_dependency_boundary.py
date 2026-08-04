"""Dependency-boundary tests for Eval production modules."""

from __future__ import annotations

import ast
from pathlib import Path


_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _EVAL_SCRIPTS.parents[1]
_FORBIDDEN_ROOTS = {"compose", "decision"}


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
    stage_modules = (
        _stage_module_names()
        - {path.stem for path in _EVAL_SCRIPTS.glob("*.py")}
        | _FORBIDDEN_ROOTS
    )
    violations = {
        path.name: sorted(_imported_module_names(path) & stage_modules)
        for path in _EVAL_SCRIPTS.glob("*.py")
    }
    assert {
        name: modules for name, modules in violations.items() if modules
    } == {}

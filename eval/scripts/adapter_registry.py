#!/usr/bin/env python3
"""Load WorkflowAdapter implementations by workflow id."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from workflow_adapter import WorkflowAdapter

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]

_REGISTRY: dict[str, tuple[str, str, str]] = {
    "tech-plan": (
        "tech-plan/scripts/eval_workflow_adapter.py",
        "eval_workflow_adapter",
        "TechPlanEvalAdapter",
    ),
}


def _load_module_from_path(module_path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load adapter module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_adapter(workflow: str) -> WorkflowAdapter:
    """Return a WorkflowAdapter for the given workflow id."""
    entry = _REGISTRY.get(workflow)
    if entry is None:
        allowed = sorted(_REGISTRY)
        raise ValueError(
            f"unknown workflow: {workflow!r} (allowed: {allowed})",
        )
    rel_path, module_name, class_name = entry
    module_path = _WORKFLOW_ROOT / rel_path
    if not module_path.is_file():
        raise FileNotFoundError(f"adapter module not found: {module_path}")
    module = _load_module_from_path(module_path, module_name)
    cls = getattr(module, class_name)
    return cls()

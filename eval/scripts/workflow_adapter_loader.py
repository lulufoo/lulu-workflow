#!/usr/bin/env python3
"""Load WorkflowAdapter implementations from compose profile eval.adapter_* fields."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from workflow_adapter import WorkflowAdapter

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]
_PROFILES_DIR = _WORKFLOW_ROOT / "compose-kernel" / "profiles"


def _load_module_from_path(module_path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load adapter module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_adapter(workflow: str) -> WorkflowAdapter:
    """Return a WorkflowAdapter for the given workflow id (compose profile id)."""
    profile_path = _PROFILES_DIR / f"{workflow}.json"
    if not profile_path.is_file():
        allowed = sorted(p.stem for p in _PROFILES_DIR.glob("*.json"))
        raise ValueError(
            f"unknown workflow: {workflow!r} (profile not found; allowed: {allowed})",
        )
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    eval_cfg = profile.get("eval") or {}
    module_rel = str(eval_cfg.get("adapter_module", "")).strip()
    class_name = str(eval_cfg.get("adapter_class", "")).strip()
    if not module_rel or not class_name:
        raise ValueError(
            f"profile {workflow!r} missing eval.adapter_module or eval.adapter_class",
        )
    module_path = _WORKFLOW_ROOT / module_rel
    if not module_path.is_file():
        raise FileNotFoundError(f"adapter module not found: {module_path}")
    module_name = module_path.stem
    module = _load_module_from_path(module_path, module_name)
    cls = getattr(module, class_name)
    return cls()

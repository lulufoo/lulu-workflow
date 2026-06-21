#!/usr/bin/env python3
"""Load StartAdapter implementations by compose profile id."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from start_adapter import StartAdapter

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]

_REGISTRY: dict[str, tuple[str, str, str]] = {
    "tech-plan": (
        "tech-plan/scripts/start/tech_plan_start_adapter.py",
        "tech_plan_start_adapter",
        "TechPlanStartAdapter",
    ),
    "tech-design": (
        "tech-design/scripts/start/tech_design_start_adapter.py",
        "tech_design_start_adapter",
        "TechDesignStartAdapter",
    ),
    "product-spec": (
        "product-spec/scripts/start/product_spec_start_adapter.py",
        "product_spec_start_adapter",
        "ProductSpecStartAdapter",
    ),
}


def _load_module_from_path(module_path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load start adapter module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_start_adapter(profile_id: str) -> StartAdapter:
    """Return a StartAdapter for the given compose profile id."""
    entry = _REGISTRY.get(profile_id)
    if entry is None:
        allowed = sorted(_REGISTRY)
        raise ValueError(
            f"unknown compose profile for start adapter: {profile_id!r} "
            f"(allowed: {allowed})",
        )
    rel_path, module_name, class_name = entry
    module_path = _WORKFLOW_ROOT / rel_path
    if not module_path.is_file():
        raise FileNotFoundError(f"start adapter module not found: {module_path}")
    module = _load_module_from_path(module_path, module_name)
    cls = getattr(module, class_name)
    return cls()

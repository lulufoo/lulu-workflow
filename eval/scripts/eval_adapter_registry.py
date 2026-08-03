#!/usr/bin/env python3
"""Validate the eval adapter registry and load registered workflow adapters."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _WORKFLOW_ROOT / "eval" / "adapter-registry.json"


@dataclass(frozen=True)
class AdapterRegistration:
    """One workflow's registered eval adapter."""

    workflow_id: str
    adapter_module: str
    adapter_class: str


def _workflow_root(workflow_root: Path | None) -> Path:
    root = (workflow_root or _WORKFLOW_ROOT).resolve()
    if not root.is_dir():
        raise ValueError(f"workflow root not found: {root.as_posix()}")
    return root


def validate_adapter_registry(payload: Any) -> dict[str, AdapterRegistration]:
    """Validate registry JSON and return registrations indexed by workflow id."""
    if not isinstance(payload, dict):
        raise ValueError("adapter registry must be a JSON object")

    workflows = payload.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        raise ValueError("adapter registry.workflows must be a non-empty list")

    registrations: dict[str, AdapterRegistration] = {}
    for index, raw_entry in enumerate(workflows):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"adapter registry.workflows[{index}] must be an object")

        workflow_id = raw_entry.get("id")
        adapter_module = raw_entry.get("adapter_module")
        adapter_class = raw_entry.get("adapter_class")
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ValueError(f"adapter registry.workflows[{index}].id is required")
        if not isinstance(adapter_module, str) or not adapter_module.strip():
            raise ValueError(
                f"adapter registry.workflows[{index}].adapter_module is required",
            )
        if not isinstance(adapter_class, str) or not adapter_class.strip():
            raise ValueError(
                f"adapter registry.workflows[{index}].adapter_class is required",
            )

        workflow_id = workflow_id.strip()
        if workflow_id in registrations:
            raise ValueError(f"duplicate workflow id: {workflow_id}")
        registrations[workflow_id] = AdapterRegistration(
            workflow_id=workflow_id,
            adapter_module=adapter_module.strip(),
            adapter_class=adapter_class.strip(),
        )
    return registrations


def load_adapter_registry(
    *,
    registry_path: Path | None = None,
    workflow_root: Path | None = None,
) -> dict[str, AdapterRegistration]:
    """Load and validate an adapter registry for a workflow root."""
    _workflow_root(workflow_root)
    path = registry_path or _REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"adapter registry not found: {path.as_posix()}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid adapter registry JSON: {path.as_posix()}") from exc
    return validate_adapter_registry(payload)


def _resolve_adapter_module(
    registration: AdapterRegistration,
    workflow_root: Path,
) -> Path:
    module_path = Path(registration.adapter_module)
    if module_path.is_absolute() or ".." in module_path.parts:
        raise ValueError(
            f"adapter_module contains path traversal: {registration.adapter_module}",
        )

    resolved_path = (workflow_root / module_path).resolve()
    try:
        resolved_path.relative_to(workflow_root)
    except ValueError as exc:
        raise ValueError(
            f"adapter_module resolves outside workflow root: "
            f"{registration.adapter_module}",
        ) from exc
    if not resolved_path.is_file():
        raise ValueError(f"adapter_module not found: {resolved_path.as_posix()}")
    return resolved_path


def load_eval_adapter(
    workflow_id: str,
    *,
    registry_path: Path | None = None,
    workflow_root: Path | None = None,
) -> Any:
    """Instantiate the adapter registered for ``workflow_id``."""
    root = _workflow_root(workflow_root)
    registrations = load_adapter_registry(
        registry_path=registry_path,
        workflow_root=root,
    )
    registration = registrations.get(workflow_id)
    if registration is None:
        raise ValueError(f"unknown eval workflow: {workflow_id}")

    adapter_path = _resolve_adapter_module(registration, root)
    module_name = "_eval_adapter_" + hashlib.sha256(
        str(adapter_path).encode("utf-8"),
    ).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(module_name, adapter_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load adapter_module: {adapter_path.as_posix()}")

    adapter_dir = str(adapter_path.parent)
    if adapter_dir not in sys.path:
        sys.path.insert(0, adapter_dir)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise

    adapter_type = getattr(module, registration.adapter_class, None)
    if adapter_type is None:
        raise ValueError(
            f"adapter class {registration.adapter_class!r} not found in "
            f"{adapter_path.as_posix()}",
        )
    if not isinstance(adapter_type, type):
        raise ValueError(
            f"adapter class {registration.adapter_class!r} is not a class in "
            f"{adapter_path.as_posix()}",
        )
    return adapter_type()

#!/usr/bin/env python3
"""Load a WorkflowAdapter from a caller-supplied JSON adapter config.

Eval does not discover stages. Callers (Compose / Decision) pass the config.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]

_REQUIRED_KEYS = ("adapter_module", "adapter_class")


@dataclass(frozen=True)
class AdapterConfig:
    """Validated adapter config payload."""

    adapter_module: str
    adapter_class: str
    workflow_id: str
    enabled: bool
    raw: dict[str, Any]


def _workflow_root(workflow_root: Path | None) -> Path:
    root = (workflow_root or _WORKFLOW_ROOT).resolve()
    if not root.is_dir():
        raise ValueError(f"workflow root not found: {root.as_posix()}")
    return root


def validate_adapter_config(payload: Any) -> AdapterConfig:
    """Validate a caller-supplied adapter config object."""
    if not isinstance(payload, dict):
        raise ValueError("adapter config must be a JSON object")

    for key in _REQUIRED_KEYS:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"adapter config.{key} must be a non-empty string")

    enabled = payload.get("enabled", True)
    if enabled is None:
        enabled = True
    if not isinstance(enabled, bool):
        raise ValueError("adapter config.enabled must be a boolean when present")
    if enabled is False:
        raise ValueError("adapter config.enabled is false; refusing to start Eval")

    adapter_module = str(payload["adapter_module"]).strip()
    adapter_class = str(payload["adapter_class"]).strip()
    workflow_id = str(payload.get("workflow_id") or "").strip() or adapter_class
    return AdapterConfig(
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        workflow_id=workflow_id,
        enabled=True,
        raw=dict(payload),
    )


def load_adapter_config_json(text: str) -> AdapterConfig:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid adapter config JSON: {exc}") from exc
    return validate_adapter_config(payload)


def load_adapter_config_file(path: Path) -> AdapterConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"adapter config not found: {path.as_posix()}") from exc
    return load_adapter_config_json(text)


def resolve_adapter_module_path(
    adapter_module: str,
    *,
    workflow_root: Path | None = None,
) -> Path:
    root = _workflow_root(workflow_root)
    module_path = Path(adapter_module)
    if module_path.is_absolute() or ".." in module_path.parts:
        raise ValueError(f"adapter_module contains path traversal: {adapter_module}")

    resolved_path = (root / module_path).resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"adapter_module resolves outside workflow root: {adapter_module}",
        ) from exc
    if not resolved_path.is_file():
        raise ValueError(f"adapter_module not found: {resolved_path.as_posix()}")
    return resolved_path


def load_eval_adapter_from_config(
    config: AdapterConfig | dict[str, Any] | str | Path,
    *,
    workflow_root: Path | None = None,
) -> Any:
    """Instantiate the adapter described by ``config``."""
    if isinstance(config, AdapterConfig):
        parsed = config
    elif isinstance(config, Path):
        parsed = load_adapter_config_file(config)
    elif isinstance(config, str):
        # Inline JSON object, or a filesystem path string.
        stripped = config.strip()
        if stripped.startswith("{"):
            parsed = load_adapter_config_json(stripped)
        else:
            parsed = load_adapter_config_file(Path(stripped))
    else:
        parsed = validate_adapter_config(config)

    root = _workflow_root(workflow_root)
    adapter_path = resolve_adapter_module_path(
        parsed.adapter_module,
        workflow_root=root,
    )
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

    adapter_type = getattr(module, parsed.adapter_class, None)
    if adapter_type is None:
        raise ValueError(
            f"adapter class {parsed.adapter_class!r} not found in "
            f"{adapter_path.as_posix()}",
        )
    if not isinstance(adapter_type, type):
        raise ValueError(
            f"adapter class {parsed.adapter_class!r} is not a class in "
            f"{adapter_path.as_posix()}",
        )
    return adapter_type()

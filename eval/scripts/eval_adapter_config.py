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

_REQUIRED_KEYS = ("adapter_module", "adapter_class", "eval_capability")
_VALID_EVAL_CAPABILITY = frozenset({"full-remediation", "probe-only"})
_READ_METHOD = "read_eval_target_digest"
_MUTATION_METHODS = ("commit_eval_target", "restore_eval_target")


@dataclass(frozen=True)
class AdapterConfig:
    """Validated adapter config payload."""

    adapter_module: str
    adapter_class: str
    workflow_id: str
    enabled: bool
    eval_capability: str
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
    eval_capability = str(payload.get("eval_capability") or "").strip()
    if eval_capability not in _VALID_EVAL_CAPABILITY:
        raise ValueError(
            "adapter config.eval_capability must be "
            "'full-remediation' or 'probe-only'",
        )
    return AdapterConfig(
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        workflow_id=workflow_id,
        enabled=True,
        eval_capability=eval_capability,
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


def _handoff_capability(handoff: dict[str, Any]) -> str:
    context = handoff.get("context") if isinstance(handoff, dict) else None
    if not isinstance(context, dict):
        return ""
    policy = context.get("policy_context")
    if isinstance(policy, dict):
        return str(policy.get("eval_capability") or "").strip()
    return ""


def _evaluate_state_capability(handoff: dict[str, Any]) -> str | None:
    """Return evaluate-state capability, or None only if the file is absent.

    A present file with a missing or invalid field is incompatible, not unchecked.
    """
    context = handoff.get("context") if isinstance(handoff, dict) else None
    if not isinstance(context, dict):
        return None
    raw_path = context.get("evaluate_state_path")
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if not path.is_file():
        return None
    found: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("eval_capability:"):
            found = line.split(":", 1)[1].strip()
            break
    if found not in _VALID_EVAL_CAPABILITY:
        raise ValueError(
            "evaluate-state exists but eval_capability is missing or invalid"
            if not found
            else f"evaluate-state eval_capability is invalid: {found!r}",
        )
    return found


def validate_adapter_protocol(
    adapter: Any,
    *,
    eval_capability: str,
    handoff: dict[str, Any],
) -> None:
    """Fail-closed if capability, methods, handoff, or evaluate-state disagree."""
    if eval_capability not in _VALID_EVAL_CAPABILITY:
        raise ValueError(f"invalid eval_capability: {eval_capability!r}")
    if not callable(getattr(adapter, _READ_METHOD, None)):
        raise ValueError(f"adapter missing required method {_READ_METHOD}")
    if eval_capability == "full-remediation":
        missing = [
            name
            for name in _MUTATION_METHODS
            if not callable(getattr(adapter, name, None))
        ]
        if missing:
            raise ValueError(
                "full-remediation adapter missing required methods: "
                + ", ".join(missing),
            )
    handoff_capability = _handoff_capability(handoff)
    if handoff_capability != eval_capability:
        raise ValueError(
            "eval_capability mismatch between config "
            f"({eval_capability!r}) and handoff ({handoff_capability!r})",
        )
    state_capability = _evaluate_state_capability(handoff)
    if state_capability is not None and state_capability != eval_capability:
        raise ValueError(
            "eval_capability mismatch between config "
            f"({eval_capability!r}) and evaluate-state ({state_capability!r})",
        )

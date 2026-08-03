"""Workflow-neutral EvalHandoff and artifact-manifest schema helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ADAPTER_REF_KEYS = frozenset(
    {
        "workflow_id",
        "adapter_module",
        "adapter_class",
        "dimension_defs_dir",
        "framework_section",
    }
)
POLICY_CONTEXT_KEYS = frozenset({"mode", "cycle_type", "upstream_baseline_ref"})
EVAL_CONTEXT_REQUIRED = frozenset(
    {
        "cycle_id",
        "profile_id",
        "focus_l",
        "pointer_fingerprint",
        "evaluate_round",
        "revision_dir",
        "slice_dir",
        "compose_doc",
        "evaluate_state_path",
        "evaluate_dir",
        "write_staging_dir",
        "lease_id",
        "layout",
        "policy_context",
    }
)
HANDOFF_REQUIRED = frozenset({"adapter", "context"})
LAYOUT_VALUES = frozenset({"per-l", "legacy-root"})
GENERIC_EVAL_CONTEXT_REQUIRED = frozenset(
    {
        "workflow_id",
        "cycle_id",
        "session_key",
        "evaluate_round",
        "evaluate_state_path",
        "evaluate_dir",
        "write_staging_dir",
        "lease_id",
        "bindings",
        "policy_context",
    }
)
GENERIC_EVAL_CONTEXT_FORBIDDEN = frozenset(
    {"compose_doc", "focus_l", "pointer_fingerprint"}
)
GENERIC_HANDOFF_REQUIRED = frozenset({"version", "context"})
GENERIC_ARTIFACT_MANIFEST_REQUIRED = frozenset(
    {
        "lease_id",
        "session_key",
        "evaluate_round",
        "staged_relative_path",
        "final_relative_path",
        "artifact_digest",
    }
)


def pointer_fingerprint(pointer: dict[str, Any]) -> str:
    """Return a stable digest of provider-owned context."""
    payload = json.dumps(pointer, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_adapter_ref(adapter: Any) -> list[str]:
    if not isinstance(adapter, dict):
        return ["adapter must be an object"]
    missing = sorted(ADAPTER_REF_KEYS - set(adapter))
    errors = [f"adapter missing keys: {', '.join(missing)}"] if missing else []
    for key in ADAPTER_REF_KEYS:
        if key in adapter and not str(adapter.get(key, "")).strip():
            errors.append(f"adapter.{key} must be non-empty")
    return errors


def _validate_policy_context(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["policy_context must be an object"]
    missing = sorted(POLICY_CONTEXT_KEYS - set(policy))
    errors = [f"policy_context missing keys: {', '.join(missing)}"] if missing else []
    return errors


def validate_eval_handoff(handoff: dict[str, Any]) -> list[str]:
    """Validate the current Compose-compatible handoff shape."""
    if not isinstance(handoff, dict):
        return ["handoff must be an object"]
    missing = sorted(HANDOFF_REQUIRED - set(handoff))
    if missing:
        return [f"handoff missing keys: {', '.join(missing)}"]
    errors = _validate_adapter_ref(handoff["adapter"])
    context = handoff.get("context")
    if not isinstance(context, dict):
        return [*errors, "context must be an object"]
    missing_context = sorted(EVAL_CONTEXT_REQUIRED - set(context))
    if missing_context:
        errors.append(f"context missing keys: {', '.join(missing_context)}")
    errors.extend(_validate_policy_context(context.get("policy_context")))
    for key in (
        "revision_dir",
        "slice_dir",
        "compose_doc",
        "evaluate_state_path",
        "evaluate_dir",
        "write_staging_dir",
    ):
        if key in context and not Path(str(context[key])).is_absolute():
            errors.append(f"context.{key} must be an absolute path")
    return errors


def build_eval_handoff_v2(
    *,
    workflow_id: str,
    cycle_id: str,
    session_key: str,
    evaluate_round: int,
    evaluate_state_path: str,
    evaluate_dir: str,
    write_staging_dir: str,
    lease_id: str,
    bindings: dict[str, Any],
    policy_context: dict[str, Any],
) -> dict[str, Any]:
    """Build the workflow-neutral v2 Eval handoff."""
    return {
        "version": 2,
        "context": {
            "workflow_id": workflow_id,
            "cycle_id": cycle_id,
            "session_key": session_key,
            "evaluate_round": int(evaluate_round),
            "evaluate_state_path": evaluate_state_path,
            "evaluate_dir": evaluate_dir,
            "write_staging_dir": write_staging_dir,
            "lease_id": lease_id,
            "bindings": bindings,
            "policy_context": policy_context,
        },
    }


def validate_eval_handoff_v2(handoff: dict[str, Any]) -> list[str]:
    """Validate the workflow-neutral v2 Eval handoff shape."""
    if not isinstance(handoff, dict):
        return ["handoff must be an object"]
    missing = sorted(GENERIC_HANDOFF_REQUIRED - set(handoff))
    if missing:
        return [f"handoff missing keys: {', '.join(missing)}"]
    errors: list[str] = []
    if handoff.get("version") != 2:
        errors.append(f"handoff.version must be 2, got {handoff.get('version')!r}")
    context = handoff.get("context")
    if not isinstance(context, dict):
        return [*errors, "context must be an object"]
    missing_context = sorted(GENERIC_EVAL_CONTEXT_REQUIRED - set(context))
    if missing_context:
        errors.append(f"context missing keys: {', '.join(missing_context)}")
    forbidden = sorted(GENERIC_EVAL_CONTEXT_FORBIDDEN & set(context))
    if forbidden:
        errors.append(f"context contains workflow-specific keys: {', '.join(forbidden)}")
    bindings = context.get("bindings")
    if not isinstance(bindings, dict):
        errors.append("context.bindings must be an object")
    elif not str(bindings.get("eval_target_path", "")).strip():
        errors.append("context.bindings.eval_target_path must be non-empty")
    errors.extend(_validate_policy_context(context.get("policy_context")))
    try:
        evaluate_round = int(context.get("evaluate_round", 0))
        if evaluate_round < 1:
            errors.append(f"evaluate_round must be >= 1, got {evaluate_round!r}")
    except (TypeError, ValueError):
        errors.append(f"invalid evaluate_round: {context.get('evaluate_round')!r}")
    for key in (
        "evaluate_state_path",
        "evaluate_dir",
        "write_staging_dir",
    ):
        if key in context and not Path(str(context[key])).is_absolute():
            errors.append(f"context.{key} must be an absolute path")
    return errors


def build_artifact_manifest_v2(
    *,
    lease_id: str,
    session_key: str,
    evaluate_round: int,
    staged_relative_path: str,
    final_relative_path: str,
    artifact_digest: str,
    state_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a workflow-neutral artifact publication manifest."""
    return {
        "lease_id": lease_id,
        "session_key": session_key,
        "evaluate_round": int(evaluate_round),
        "staged_relative_path": staged_relative_path,
        "final_relative_path": final_relative_path,
        "artifact_digest": artifact_digest,
        "state_patch": state_patch or {},
    }


def validate_artifact_manifest_v2(manifest: dict[str, Any]) -> list[str]:
    """Validate a workflow-neutral artifact publication manifest."""
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    missing = sorted(GENERIC_ARTIFACT_MANIFEST_REQUIRED - set(manifest))
    errors = [f"manifest missing keys: {', '.join(missing)}"] if missing else []
    forbidden = sorted(GENERIC_EVAL_CONTEXT_FORBIDDEN & set(manifest))
    if forbidden:
        errors.append(f"manifest contains workflow-specific keys: {', '.join(forbidden)}")
    if "state_patch" in manifest and not isinstance(manifest["state_patch"], dict):
        errors.append("manifest.state_patch must be an object")
    return errors


def build_artifact_manifest(
    *,
    lease_id: str,
    pointer_fingerprint_value: str,
    focus_l: str,
    evaluate_round: int,
    staged_relative_path: str,
    final_relative_path: str,
    artifact_digest: str,
    state_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the provider-validated artifact publication manifest."""
    return {
        "lease_id": lease_id,
        "pointer_fingerprint": pointer_fingerprint_value,
        "focus_l": focus_l,
        "evaluate_round": int(evaluate_round),
        "staged_relative_path": staged_relative_path,
        "final_relative_path": final_relative_path,
        "artifact_digest": artifact_digest,
        "state_patch": state_patch or {},
    }


def validate_artifact_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate a review publication manifest before provider commit."""
    required = {
        "lease_id",
        "pointer_fingerprint",
        "focus_l",
        "evaluate_round",
        "staged_relative_path",
        "final_relative_path",
        "artifact_digest",
    }
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    missing = sorted(required - set(manifest))
    errors = [f"manifest missing keys: {', '.join(missing)}"] if missing else []
    if "state_patch" in manifest and not isinstance(manifest["state_patch"], dict):
        errors.append("manifest.state_patch must be an object")
    return errors

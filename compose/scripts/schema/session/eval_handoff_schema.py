#!/usr/bin/env python3
"""Schema helpers for Compose → Eval EvalHandoff (AdapterRef + EvalContext).

Handoff is a runtime JSON object — not persisted as session SSOT.
"""

from __future__ import annotations

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
        "ledger_fingerprint",
        "eval_run_id",
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
LAYOUT_VALUES = frozenset({"per-l"})


def validate_adapter_ref(adapter: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(adapter, dict):
        return ["adapter must be an object"]
    missing = sorted(ADAPTER_REF_KEYS - set(adapter))
    if missing:
        errors.append(f"adapter missing keys: {', '.join(missing)}")
    for key in ADAPTER_REF_KEYS:
        if key in adapter and not str(adapter.get(key, "")).strip():
            errors.append(f"adapter.{key} must be non-empty")
    return errors


def validate_policy_context(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(policy, dict):
        return ["policy_context must be an object"]
    missing = sorted(POLICY_CONTEXT_KEYS - set(policy))
    if missing:
        errors.append(f"policy_context missing keys: {', '.join(missing)}")
    mode = str(policy.get("mode", ""))
    if mode and mode not in {"product", "tech"}:
        errors.append(f"invalid policy_context.mode: {mode!r}")
    cycle_type = str(policy.get("cycle_type", ""))
    if cycle_type and cycle_type not in {"topic", "feature"}:
        errors.append(f"invalid policy_context.cycle_type: {cycle_type!r}")
    return errors


def validate_eval_context(context: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(context, dict):
        return ["context must be an object"]
    missing = sorted(EVAL_CONTEXT_REQUIRED - set(context))
    if missing:
        errors.append(f"context missing keys: {', '.join(missing)}")
    layout = str(context.get("layout", ""))
    if layout and layout not in LAYOUT_VALUES:
        errors.append(f"invalid context.layout: {layout!r}")
    try:
        round_n = int(context.get("evaluate_round", 0))
        if round_n < 1:
            errors.append(f"evaluate_round must be >= 1, got {round_n!r}")
    except (TypeError, ValueError):
        errors.append(f"invalid evaluate_round: {context.get('evaluate_round')!r}")
    if "policy_context" in context:
        errors.extend(validate_policy_context(context["policy_context"]))
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


def validate_eval_handoff(handoff: dict[str, Any]) -> list[str]:
    if not isinstance(handoff, dict):
        return ["handoff must be an object"]
    errors: list[str] = []
    missing = sorted(HANDOFF_REQUIRED - set(handoff))
    if missing:
        errors.append(f"handoff missing keys: {', '.join(missing)}")
        return errors
    errors.extend(validate_adapter_ref(handoff["adapter"]))
    errors.extend(validate_eval_context(handoff["context"]))
    return errors


def build_artifact_manifest(
    *,
    lease_id: str,
    ledger_fingerprint_value: str,
    eval_run_id: str,
    focus_l: str,
    evaluate_round: int,
    staged_relative_path: str,
    final_relative_path: str,
    artifact_digest: str,
    state_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "lease_id": lease_id,
        "ledger_fingerprint": ledger_fingerprint_value,
        "eval_run_id": eval_run_id,
        "focus_l": focus_l,
        "evaluate_round": int(evaluate_round),
        "staged_relative_path": staged_relative_path,
        "final_relative_path": final_relative_path,
        "artifact_digest": artifact_digest,
        "state_patch": state_patch or {},
    }


def validate_artifact_manifest(manifest: dict[str, Any]) -> list[str]:
    required = {
        "lease_id",
        "ledger_fingerprint",
        "eval_run_id",
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

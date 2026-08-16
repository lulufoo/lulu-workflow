#!/usr/bin/env python3
"""Derive the Compose Eval runtime adapter envelope from a stage profile."""

from __future__ import annotations

import hashlib
import json
from typing import Any

OUTER_ADAPTER_MODULE = "compose/scripts/core/compose_eval_adapter.py"
OUTER_ADAPTER_CLASS = "ComposeEvalAdapter"


def canonical_profile_digest(profile: dict[str, Any]) -> str:
    """Return SHA256 of the canonical profile JSON."""
    payload = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_compose_eval_envelope(profile: dict[str, Any]) -> dict[str, Any]:
    """Build the decorator envelope Eval Loader consumes.

    Stage profile is the Contributor SSOT. This envelope is derived runtime
    data, not a second configuration source.
    """
    eval_block = profile.get("eval")
    if not isinstance(eval_block, dict):
        raise ValueError("compose-profile.json missing object field 'eval'")
    workflow_id = str(eval_block.get("workflow_id") or "").strip()
    contributor_module = str(eval_block.get("contributor_module") or "").strip()
    contributor_class = str(eval_block.get("contributor_class") or "").strip()
    eval_capability = str(eval_block.get("eval_capability") or "").strip()
    if not workflow_id or not contributor_module or not contributor_class:
        raise ValueError(
            "compose-profile.json eval must include workflow_id, "
            "contributor_module, and contributor_class",
        )
    if not eval_capability:
        raise ValueError("compose-profile.json eval.eval_capability is required")
    if eval_block.get("enabled") is False:
        raise ValueError("profile.eval.enabled is false")
    return {
        "adapter_module": OUTER_ADAPTER_MODULE,
        "adapter_class": OUTER_ADAPTER_CLASS,
        "workflow_id": workflow_id,
        "eval_capability": eval_capability,
        "enabled": True,
        "profile_digest": canonical_profile_digest(profile),
        "construction": "decorator",
        "adapter_options": {
            "delegate": {
                "module": contributor_module,
                "class": contributor_class,
            }
        },
    }

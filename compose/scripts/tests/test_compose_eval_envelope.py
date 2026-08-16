#!/usr/bin/env python3
"""Tests for Compose Eval runtime envelope derivation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bootstrap  # noqa: F401

from compose_eval_envelope import (  # noqa: E402
    OUTER_ADAPTER_CLASS,
    build_compose_eval_envelope,
    canonical_profile_digest,
)


def _profile() -> dict:
    return {
        "profile_id": "lulu-design",
        "eval": {
            "enabled": True,
            "workflow_id": "lulu-design",
            "contributor_module": "lulu-design/scripts/eval/tech_design_eval_contributor.py",
            "contributor_class": "TechDesignEvalContributor",
            "eval_capability": "full-remediation",
        },
    }


def test_envelope_points_at_outer_adapter() -> None:
    envelope = build_compose_eval_envelope(_profile())
    assert envelope["adapter_class"] == OUTER_ADAPTER_CLASS
    assert envelope["construction"] == "decorator"
    assert envelope["adapter_options"]["delegate"]["class"] == "TechDesignEvalContributor"
    assert envelope["profile_digest"] == canonical_profile_digest(_profile())


def test_digest_changes_when_profile_changes() -> None:
    first = canonical_profile_digest(_profile())
    changed = _profile()
    changed["eval"] = dict(changed["eval"])
    changed["eval"]["eval_capability"] = "probe-only"
    assert canonical_profile_digest(changed) != first


def test_real_profiles_build_envelopes() -> None:
    workflow_root = Path(__file__).resolve().parents[3]
    for stage in ("lulu-plan", "lulu-design", "lulu-arch", "lulu-blueprint", "lulu-spec"):
        profile = json.loads(
            (workflow_root / stage / "compose-profile.json").read_text(encoding="utf-8")
        )
        envelope = build_compose_eval_envelope(profile)
        assert envelope["workflow_id"] == stage
        assert envelope["adapter_class"] == OUTER_ADAPTER_CLASS


def test_rejects_missing_contributor() -> None:
    with pytest.raises(ValueError, match="contributor_module"):
        build_compose_eval_envelope({"eval": {"enabled": True, "workflow_id": "x"}})

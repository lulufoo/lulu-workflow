"""Tests for Compose's private-to-generic Eval handoff translation."""

from __future__ import annotations

import sys
from pathlib import Path

_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_COMPOSE_CORE = _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "core"
for path in (_COMPOSE_CORE, _EVAL_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import compose_eval_adapter_support
from compose_eval_adapter_support import ComposeEvalAdapterSupport
from eval_handoff_schema import validate_eval_handoff_v2


class _Support(ComposeEvalAdapterSupport):
    WORKFLOW_ID = "lulu-design"


def test_request_handoff_translates_compose_context_to_generic_v2(
    monkeypatch,
    tmp_path: Path,
) -> None:
    legacy_context = {
        "cycle_id": "cycle-1",
        "profile_id": "lulu-design",
        "focus_l": "L3",
        "pointer_fingerprint": "private-pointer-fingerprint",
        "evaluate_round": 2,
        "revision_dir": "/tmp/revision1",
        "slice_dir": "/tmp/revision1/L3",
        "compose_doc": "/tmp/revision1/design-doc.md",
        "evaluate_state_path": "/tmp/revision1/L3/evaluate-state.md",
        "evaluate_dir": "/tmp/revision1/L3/evaluate2",
        "write_staging_dir": "/tmp/revision1/L3/.eval-staging/lease-1",
        "lease_id": "lease-1",
        "layout": "per-l",
        "policy_context": {
            "mode": "tech",
            "cycle_type": "feature",
            "upstream_baseline_ref": "",
        },
    }
    monkeypatch.setattr(
        compose_eval_adapter_support,
        "request_handoff",
        lambda *args, **kwargs: {"ok": True, "handoff": {"context": legacy_context}},
    )

    handoff = _Support().request_eval_handoff("cycle-1", tmp_path)

    assert validate_eval_handoff_v2(handoff) == []
    assert handoff["context"]["workflow_id"] == "lulu-design"
    assert handoff["context"]["cycle_id"] == "cycle-1"
    assert handoff["context"]["session_key"] == "L3"
    assert handoff["context"]["bindings"] == {
        "eval_target_path": "/tmp/revision1/design-doc.md",
    }
    assert {"compose_doc", "focus_l", "pointer_fingerprint"}.isdisjoint(
        handoff["context"],
    )

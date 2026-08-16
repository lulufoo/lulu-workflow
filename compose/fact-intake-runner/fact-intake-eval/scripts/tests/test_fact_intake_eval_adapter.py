#!/usr/bin/env python3
"""Tests for Fact Intake Eval adapter (no StageGate; B=_facts.json)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

# .../compose/fact-intake-runner/fact-intake-eval/scripts/tests/<this>
_ATOMIZE = Path(__file__).resolve().parents[1]  # fact-intake-eval/scripts
_COMPOSE_SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"  # compose/scripts
_COMPOSE_CORE = _COMPOSE_SCRIPTS / "core"
_COMPOSE_TESTS = _COMPOSE_SCRIPTS / "tests"
_EVAL = Path(__file__).resolve().parents[5] / "eval" / "scripts"  # lulu-dev-workflow/eval/scripts
for p in (_ATOMIZE, _COMPOSE_CORE, _COMPOSE_TESTS, _EVAL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import bootstrap  # noqa: F401, E402
from bootstrap import CORE  # noqa: E402

sys.path.insert(0, str(CORE))

from fact_intake_eval_adapter import (  # noqa: E402
    FactIntakeEvalAdapter,
    _PROFILE_ENV,
    _init_evaluate_state,
)
from fact_intake_eval_runtime_schema import evaluate_state_path, load_runtime, runtime_path  # noqa: E402
from l_ledger_schema import active_slice_dir  # noqa: E402
from facts_schema import FACTS_BASENAME  # noqa: E402
from init_working_helpers import init_working_ready  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests  # noqa: E402
from evaluate_state_schema import (  # noqa: E402
    load_evaluate_state,
    parse_force_human_resolution,
)

_CYCLE = "feat-fact-intake-eval"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed(tmp_path: Path) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, DEFAULT_COMPOSE_PROFILE_ID)
    base = tmp_path / _CACHE / _CYCLE / "lulu-plan"
    base.mkdir(parents=True, exist_ok=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    ws = base / "revision1" / "workflow-state.md"
    init_working_ready(ws, mode="tech")
    rev = ws.parent
    slice_dir = active_slice_dir(rev)
    (slice_dir / FACTS_BASENAME).write_text(
        json.dumps(
            {
                "version": "1",
                "facts": [
                    {
                        "id": "F-1",
                        "text": "fact",
                        "lens_tags": ["CTX"],
                        "derivation": {
                            "disposition": "carried",
                            "upstream_ref": ["src"],
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return rev


def test_enter_evaluating_skips_stage_gate(tmp_path: Path, monkeypatch) -> None:
    rev = _seed(tmp_path)
    monkeypatch.setenv(_PROFILE_ENV, "lulu-plan")
    adapter = FactIntakeEvalAdapter()
    result = adapter.enter_evaluating(_CYCLE, tmp_path)
    assert result["ok"] is True
    assert result["transitioned"] is True
    slice_dir = active_slice_dir(rev)
    assert (slice_dir / "fact-intake-eval" / "evaluate-state.md").is_file()
    runtime = load_runtime(runtime_path(slice_dir))
    assert runtime["focus_phase"] == "evaluating"
    # Delivery Evaluating state must not be created at slice root.
    assert not (slice_dir / "evaluate-state.md").is_file()
    assert not (rev / "evaluate-state.md").is_file()


def test_initial_state_copies_policy_from_resolved_corpus(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed(tmp_path)
    monkeypatch.setenv(_PROFILE_ENV, "lulu-plan")
    corpus = FactIntakeEvalAdapter().resolve_eval_corpus(_CYCLE, tmp_path)
    corpus["dimensions"][0]["force_human_resolution"] = True
    path = tmp_path / "evaluate-state.md"
    _init_evaluate_state(path, corpus, evaluate_round=1, focus_l="L1")
    state = load_evaluate_state(path)
    assert parse_force_human_resolution(state["force_human_resolution"]) == {
        "e1-doc-coverage": True,
        "e2-fact-provenance": False,
    }


def test_handoff_binds_facts_json(tmp_path: Path, monkeypatch) -> None:
    rev = _seed(tmp_path)
    monkeypatch.setenv(_PROFILE_ENV, "lulu-plan")
    adapter = FactIntakeEvalAdapter()
    assert adapter.enter_evaluating(_CYCLE, tmp_path)["ok"] is True
    handoff = adapter.request_eval_handoff(_CYCLE, tmp_path, require_evaluating=True)
    bindings = handoff["context"]["bindings"]
    assert bindings["eval_target_path"].endswith(FACTS_BASENAME)
    assert handoff["context"]["policy_context"]["completion_mode"] == "return_to_caller"
    assert Path(bindings["eval_target_path"]).is_file()
    assert "fact-intake-eval" in handoff["context"]["evaluate_state_path"]
    assert evaluate_state_path(active_slice_dir(rev)).is_file()


def test_commit_remediation_writes_facts(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path)
    monkeypatch.setenv(_PROFILE_ENV, "lulu-plan")
    adapter = FactIntakeEvalAdapter()
    assert adapter.enter_evaluating(_CYCLE, tmp_path)["ok"] is True
    handoff = adapter.request_eval_handoff(_CYCLE, tmp_path)
    staging = Path(handoff["context"]["write_staging_dir"])
    target = Path(handoff["context"]["bindings"]["eval_target_path"])
    base = hashlib.sha256(target.read_bytes()).hexdigest()
    staged = staging / "target.remediated"
    staged.write_text('{"version":"1","facts":[]}\n', encoding="utf-8")
    result = adapter.commit_remediation_target(
        _CYCLE,
        tmp_path,
        staged_target_path=staged,
        base_digest=base,
        lease_id=str(handoff["context"]["lease_id"]),
    )
    assert result["ok"] is True
    assert '"facts":[]' in target.read_text(encoding="utf-8").replace(" ", "")

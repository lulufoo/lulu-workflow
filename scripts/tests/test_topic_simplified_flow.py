"""Topic Bet and Approach are independent entry decisions: any order, no hand-off."""
import json
from pathlib import Path

import pytest

from context_loading import build_context_loading
from start_gate import check_gate
from transition_table import allowed_stages, load_transitions, next_steps_for_stage
from workflow_sessions import current_effective_delivered

_TOPIC_STAGES = ("lulu-bet", "lulu-approach")


def _delivered_bet(cache: Path, cycle: str) -> Path:
    root = cache / cycle / "lulu-bet"
    root.mkdir(parents=True)
    doc = root / "decision-doc.md"
    doc.write_text("# Bet decision\n", encoding="utf-8")
    (root / "session-state.md").write_text("---\ncurrent_state: Completed\n---\n")
    package = root / "decision-package.json"
    package.write_text(json.dumps({"version": 2, "status": "package_ready", "main": {"decision_doc_path": "decision-doc.md"}}))
    refs = cache / cycle / "delivered-refs.json"
    refs.write_text(json.dumps({"version": 1, "entries": {"lulu-bet": {"artifact": "decision-package", "path": str(package)}}}))
    return doc


def test_topic_table_declares_only_entry_stages():
    assert load_transitions("topic") == {None: set(_TOPIC_STAGES)}
    for stage in _TOPIC_STAGES:
        assert next_steps_for_stage(stage, "topic") == []
    assert set(_TOPIC_STAGES) <= allowed_stages("topic")
    assert "lulu-brainstorm" not in allowed_stages("topic")


@pytest.mark.parametrize("current", [None, *_TOPIC_STAGES])
@pytest.mark.parametrize("target", _TOPIC_STAGES)
def test_topic_gate_accepts_either_decision_at_any_time(tmp_path: Path, current, target):
    cycle = "topic-either-order"
    (tmp_path / cycle).mkdir()
    if current is not None:
        (tmp_path / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": current}))
    assert check_gate(cycle, target, "topic", tmp_path)[0]


def test_topic_approach_context_ignores_delivered_bet(tmp_path: Path):
    _delivered_bet(tmp_path, "topic-test")
    assert build_context_loading("topic-test", "lulu-approach", cache_dir=tmp_path)["docs"] == {}


def test_reopening_topic_bet_leaves_approach_delivered(tmp_path: Path):
    from dec_gate_control import cmd_reopen
    from dec_session_state_schema import write_session_state
    from dec_workflow_common import CACHE_DIR

    cycle = "topic-reopen"
    cache = tmp_path / CACHE_DIR
    doc = _delivered_bet(cache, cycle)
    (doc.parent / "gate-state.json").write_text("{}")
    approach = cache / cycle / "lulu-approach"
    approach.mkdir()
    write_session_state(approach / "session-state.md", "Completed")
    refs = cache / cycle / "delivered-refs.json"
    data = json.loads(refs.read_text())
    data["entries"]["lulu-approach"] = {"artifact": "decision-package", "path": str(approach / "decision-package.json")}
    refs.write_text(json.dumps(data))

    assert cmd_reopen(tmp_path, cycle, "lulu-bet", session_dir=doc.parent) == 0

    assert "lulu-approach" in json.loads(refs.read_text())["entries"]
    assert current_effective_delivered(cycle, "lulu-approach", cache)
    assert "Invalidated" not in (approach / "session-state.md").read_text()

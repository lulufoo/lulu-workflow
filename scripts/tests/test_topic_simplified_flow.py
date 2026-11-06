"""Topic decisions hand off a delivered Bet and invalidate stale work on reopen."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from context_loading import build_context_loading
from start_gate import check_gate
from transition_table import known_stages, next_steps_for_stage
from workflow_sessions import current_effective_delivered, delivered_bet_decision_doc


def _bet(cache: Path, cycle: str) -> tuple[Path, Path]:
    root = cache / cycle / "lulu-bet"
    root.mkdir(parents=True)
    doc = root / "decision-doc.md"
    doc.write_text("# Bet decision\n", encoding="utf-8")
    (root / "session-state.md").write_text("---\ncurrent_state: Completed\n---\n")
    package = root / "decision-package.json"
    package.write_text(json.dumps({"version": 2, "status": "package_ready", "main": {"decision_doc_path": "decision-doc.md"}}))
    refs = cache / cycle / "delivered-refs.json"
    refs.write_text(json.dumps({"version": 1, "entries": {"lulu-bet": {"artifact": "decision-package", "path": str(package)}}}))
    return doc, refs


def test_topic_starts_and_transitions_without_compose_stages(tmp_path: Path):
    assert known_stages("topic") == {"lulu-bet", "lulu-approach"}
    assert next_steps_for_stage("lulu-bet", "topic") == ["lulu-approach"]
    assert next_steps_for_stage("lulu-approach", "topic") == []
    assert check_gate("topic-pure", "lulu-approach", "topic", tmp_path)[0]
    assert not check_gate("topic-pure", "lulu-blueprint", "topic", tmp_path)[0]
    assert not check_gate("topic-pure", "lulu-arch", "topic", tmp_path)[0]


def test_topic_bet_requires_delivery_and_supplies_approach_context(tmp_path: Path):
    cycle = "topic-test"
    doc, refs = _bet(tmp_path, cycle)
    (tmp_path / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-bet"}))
    assert check_gate(cycle, "lulu-approach", "topic", tmp_path)[0]
    assert build_context_loading(cycle, "lulu-approach", cache_dir=tmp_path)["docs"] == {"product_decision": str(doc)}
    refs.unlink()
    assert not check_gate(cycle, "lulu-approach", "topic", tmp_path)[0]
    assert build_context_loading(cycle, "lulu-approach", cache_dir=tmp_path)["docs"] == {}
    assert doc.is_file()


def test_bet_package_validates_schema_and_cannot_escape_holder(tmp_path: Path):
    cycle = "topic-test"
    doc, refs = _bet(tmp_path, cycle)
    package = doc.parent / "decision-package.json"
    data = json.loads(package.read_text())
    data["version"] = 1
    package.write_text(json.dumps(data))
    assert delivered_bet_decision_doc(cycle, tmp_path) is None
    outside_package = tmp_path / "decision-package.json"
    outside_package.write_text(json.dumps({**data, "version": 2}))
    entries = json.loads(refs.read_text())
    entries["entries"]["lulu-bet"]["path"] = str(outside_package)
    refs.write_text(json.dumps(entries))
    assert delivered_bet_decision_doc(cycle, tmp_path) is None
    entries["entries"]["lulu-bet"]["path"] = str(package)
    refs.write_text(json.dumps(entries))
    data["version"] = 2
    outside = tmp_path / "outside.md"
    outside.write_text("outside")
    link = doc.parent / "linked.md"
    link.symlink_to(outside)
    data["main"]["decision_doc_path"] = "linked.md"
    package.write_text(json.dumps(data))
    assert delivered_bet_decision_doc(cycle, tmp_path) is None


def test_reopening_topic_bet_revokes_delivery_and_invalidates_approach(tmp_path: Path):
    from dec_gate_control import cmd_reopen
    from dec_session_state_schema import write_session_state
    from dec_workflow_common import CACHE_DIR

    cycle = "topic-reopen"
    cache = tmp_path / CACHE_DIR
    doc, refs = _bet(cache, cycle)
    bet = doc.parent
    (bet / "gate-state.json").write_text("{}")
    approach = cache / cycle / "lulu-approach"
    approach.mkdir()
    write_session_state(approach / "session-state.md", "Completed")
    data = json.loads(refs.read_text())
    data["entries"]["lulu-approach"] = {"artifact": "decision-package", "path": str(approach / "decision-package.json")}
    refs.write_text(json.dumps(data))

    assert cmd_reopen(tmp_path, cycle, "lulu-bet", session_dir=bet) == 0
    assert "lulu-bet" not in json.loads(refs.read_text())["entries"]
    assert "lulu-approach" not in json.loads(refs.read_text())["entries"]
    assert not current_effective_delivered(cycle, "lulu-approach", cache)
    assert "Invalidated" in (approach / "session-state.md").read_text()
    assert doc.is_file()
    # Completing the revised session does not re-create the delivery reference.
    write_session_state(bet / "session-state.md", "Completed")
    (cache / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-approach"}))
    assert not check_gate(cycle, "lulu-approach", "topic", cache)[0]


def test_failed_topic_bet_reopen_restores_refs_and_downstream(tmp_path: Path, monkeypatch):
    import dec_gate_control
    from dec_session_state_schema import write_session_state
    from dec_workflow_common import CACHE_DIR

    cycle = "topic-failing-reopen"
    cache = tmp_path / CACHE_DIR
    doc, refs = _bet(cache, cycle)
    (doc.parent / "gate-state.json").write_text("{}")
    approach = cache / cycle / "lulu-approach"
    approach.mkdir()
    state = approach / "session-state.md"
    write_session_state(state, "Completed")
    data = json.loads(refs.read_text())
    data["entries"]["lulu-approach"] = {"artifact": "decision-package", "path": str(approach / "decision-package.json")}
    refs.write_text(json.dumps(data))
    before_refs, before_state = refs.read_bytes(), state.read_bytes()

    def fail(_root):
        raise OSError("injected freeze failure")

    monkeypatch.setattr(dec_gate_control, "set_session_frozen", fail)
    assert dec_gate_control.cmd_reopen(tmp_path, cycle, "lulu-bet", session_dir=doc.parent) != 0
    assert refs.read_bytes() == before_refs
    assert state.read_bytes() == before_state


def test_pure_tech_topic_can_reenter_approach(tmp_path: Path):
    cycle = "topic-pure"
    (tmp_path / cycle).mkdir()
    (tmp_path / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-approach"}))
    assert check_gate(cycle, "lulu-approach", "topic", tmp_path)[0]
    bet = tmp_path / cycle / "lulu-bet"
    bet.mkdir()
    (bet / "session-state.md").write_text("---\ncurrent_state: Invalidated\n---\n")
    assert check_gate(cycle, "lulu-approach", "topic", tmp_path)[0]


@pytest.mark.parametrize("package_version", [2, 1], ids=["valid-package", "invalid-package"])
def test_approach_reentry_blocks_when_bet_state_is_missing(tmp_path: Path, package_version: int):
    cycle = "topic-missing-bet-state"
    doc, refs = _bet(tmp_path, cycle)
    (doc.parent / "session-state.md").unlink()
    package = doc.parent / "decision-package.json"
    data = json.loads(package.read_text())
    data["version"] = package_version
    package.write_text(json.dumps(data))
    (tmp_path / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-approach"}))
    assert not check_gate(cycle, "lulu-approach", "topic", tmp_path)[0]


def test_starting_new_topic_bet_revokes_previous_delivery(tmp_path: Path):
    from dec_workflow_common import CACHE_DIR

    cycle = "topic-start-again"
    cache = tmp_path / CACHE_DIR
    doc, refs = _bet(cache, cycle)
    (cache / "cycles.json").write_text(json.dumps({cycle: {"name": "topic"}}))
    (cache / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-bet"}))
    config = tmp_path / ".cursor" / "lulu-workflow"
    config.mkdir(parents=True)
    template = tmp_path / "template.md"
    template.write_text("# Decision\n")
    (config / "workflow-config.json").write_text(json.dumps({"decision": {"decision_doc_template_url": template.as_uri()}}))
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "decision/scripts/dec_start.py"), "--project-root", str(tmp_path),
         "--cycle-id", cycle, "--constraints", str(root / "lulu-bet/constraints-topic.json")],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "lulu-bet" not in json.loads(refs.read_text())["entries"]
    assert doc.is_file()


def test_rejected_topic_bet_start_preserves_existing_delivery(tmp_path: Path):
    from dec_workflow_common import CACHE_DIR

    cycle = "topic-rejected-start"
    cache = tmp_path / CACHE_DIR
    doc, refs = _bet(cache, cycle)
    (cache / "cycles.json").write_text(json.dumps({cycle: {"name": "topic"}}))
    (cache / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-approach"}))
    approach = cache / cycle / "lulu-approach"
    approach.mkdir()
    state = approach / "session-state.md"
    state.write_text("---\ncurrent_state: Completed\n---\n")
    before = refs.read_bytes()
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "decision/scripts/dec_start.py"), "--project-root", str(tmp_path),
         "--cycle-id", cycle, "--constraints", str(root / "lulu-bet/constraints-topic.json")],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode != 0
    assert refs.read_bytes() == before
    assert "Completed" in state.read_text()
    assert doc.is_file()


def test_invalid_domain_override_does_not_retire_bet(tmp_path: Path):
    from dec_workflow_common import CACHE_DIR

    cycle = "topic-invalid-input"
    cache = tmp_path / CACHE_DIR
    doc, refs = _bet(cache, cycle)
    (cache / "cycles.json").write_text(json.dumps({cycle: {"name": "topic"}}))
    (cache / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-bet"}))
    before = refs.read_bytes()
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "decision/scripts/dec_start.py"), "--project-root", str(tmp_path),
         "--cycle-id", cycle, "--constraints", str(root / "lulu-bet/constraints-topic.json"),
         "--domain-constraints-file", str(tmp_path / "missing.json")],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode != 0
    assert refs.read_bytes() == before
    assert doc.is_file()


def test_existing_bet_session_start_does_not_retire_delivery(tmp_path: Path):
    from dec_workflow_common import CACHE_DIR

    cycle = "topic-existing-bet"
    cache = tmp_path / CACHE_DIR
    doc, refs = _bet(cache, cycle)
    (doc.parent / "gate-state.json").write_text("{}")
    (cache / "cycles.json").write_text(json.dumps({cycle: {"name": "topic"}}))
    (cache / cycle / "cycle-state.json").write_text(json.dumps({"current_stage": "lulu-bet"}))
    before = refs.read_bytes()
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "decision/scripts/dec_start.py"), "--project-root", str(tmp_path),
         "--cycle-id", cycle, "--constraints", str(root / "lulu-bet/constraints-topic.json")],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "$DEC_REOPEN" in result.stderr
    assert refs.read_bytes() == before

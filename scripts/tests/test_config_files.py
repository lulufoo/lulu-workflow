"""Tests for lulu-dev-workflow/config/ JSON configuration files."""
import json
import pathlib

CONFIG_DIR = pathlib.Path(__file__).resolve().parents[2] / "config"


def load(filename):
    with open(CONFIG_DIR / filename) as f:
        return json.load(f)


def test_transition_table_parseable():
    data = load("transition-table.json")
    assert isinstance(data, dict)


def test_transition_table_version():
    data = load("transition-table.json")
    assert data["version"] == 2


def test_transition_table_topic_count():
    data = load("transition-table.json")
    assert len(data["topic"]) == 7


def test_transition_table_feature_count():
    data = load("transition-table.json")
    assert len(data["feature"]) == 8


def test_transition_table_topic_last_entry():
    data = load("transition-table.json")
    last = data["topic"][-1]
    assert last["from"] == "tech-plan"
    assert last["to"] == []


def test_transition_table_has_topic_doc_stage():
    data = load("transition-table.json")
    assert "topic_doc_stage" in data


def test_topic_doc_stage_tech_code_is_null():
    data = load("transition-table.json")
    assert data["topic_doc_stage"]["tech-code"] is None


def test_topic_doc_stage_key_count():
    data = load("transition-table.json")
    assert len(data["topic_doc_stage"]) == 7


def test_transition_table_null_entries_feature():
    data = load("transition-table.json")
    null_entries = [e for e in data["feature"] if e.get("from") is None]
    null_targets = {t for e in null_entries for t in e.get("to", [])}
    assert "product-diagnostic" in null_targets
    assert "tech-diagnostic" in null_targets


def test_no_old_state_names():
    old_names = ["InProgress", "ReadyForDelivery"]
    raw = (CONFIG_DIR / "transition-table.json").read_text()
    for name in old_names:
        assert name not in raw, f"Found old state name '{name}' in transition-table.json"

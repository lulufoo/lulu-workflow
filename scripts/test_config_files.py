"""Tests for lulu-dev-workflow/config/ JSON configuration files."""
import json
import pathlib

CONFIG_DIR = pathlib.Path(__file__).parent.parent / "config"


def load(filename):
    with open(CONFIG_DIR / filename) as f:
        return json.load(f)


def test_all_files_parseable():
    for name in ("state-machine.json", "gate-model.json", "transition-table.json"):
        data = load(name)
        assert isinstance(data, dict)


def test_state_machine_version():
    data = load("state-machine.json")
    assert data["version"] == 2


def test_state_machine_cycle_types_keys():
    data = load("state-machine.json")
    assert "topic" in data["cycle_types"]
    assert "feature" in data["cycle_types"]


def test_topic_stages_count():
    data = load("state-machine.json")
    assert len(data["cycle_types"]["topic"]["stages"]) == 4


def test_feature_stages_count():
    data = load("state-machine.json")
    assert len(data["cycle_types"]["feature"]["stages"]) == 6


def test_topic_doc_stage_tech_code_is_null():
    data = load("state-machine.json")
    assert data["topic_doc_stage"]["tech-code"] is None


def test_topic_doc_stage_key_count():
    data = load("state-machine.json")
    assert len(data["topic_doc_stage"]) == 6


def test_gate_model_version():
    data = load("gate-model.json")
    assert data["version"] == 2


def test_gate_model_rule():
    data = load("gate-model.json")
    assert data["rule"] == "sequential_all_prior"


def test_transition_table_version():
    data = load("transition-table.json")
    assert data["version"] == 2


def test_transition_table_topic_count():
    data = load("transition-table.json")
    assert len(data["topic"]) == 5


def test_transition_table_feature_count():
    data = load("transition-table.json")
    assert len(data["feature"]) == 7


def test_transition_table_topic_last_entry():
    data = load("transition-table.json")
    last = data["topic"][-1]
    assert last["from"] == "tech-plan"
    assert last["to"] == []


def test_no_old_state_names():
    old_names = ["InProgress", "ReadyForDelivery"]
    for filename in ("state-machine.json", "gate-model.json", "transition-table.json"):
        raw = (CONFIG_DIR / filename).read_text()
        for name in old_names:
            assert name not in raw, f"Found old state name '{name}' in {filename}"

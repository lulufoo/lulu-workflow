#!/usr/bin/env python3
"""Tests for cycle_schema.py and cycle_control.py start."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
_CYCLE_CONTROL = _SCRIPTS / "cycle_control.py"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_CYCLE_ID_RE = re.compile(r"^(feature|topic)-\d{14}-[0-9a-f]{8}$")


# ---------------------------------------------------------------------------
# generate_cycle_id
# ---------------------------------------------------------------------------

class TestGenerateFeatureId:
    def test_format_matches_pattern(self):
        from cycle_schema import generate_cycle_id
        fid = generate_cycle_id("feature")
        assert _CYCLE_ID_RE.match(fid), f"Bad format: {fid!r}"

    def test_timestamp_part_is_14_digits(self):
        from cycle_schema import generate_cycle_id
        fid = generate_cycle_id("feature")
        ts_part = fid.split("-")[1]
        assert len(ts_part) == 14
        assert ts_part.isdigit()

    def test_hex_part_is_8_lowercase_chars(self):
        from cycle_schema import generate_cycle_id
        fid = generate_cycle_id("feature")
        hex_part = fid.split("-")[2]
        assert len(hex_part) == 8
        assert hex_part == hex_part.lower()
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_consecutive_calls_produce_unique_ids(self):
        from cycle_schema import generate_cycle_id
        ids = [generate_cycle_id("feature") for _ in range(10)]
        assert len(set(ids)) == 10, "Duplicate cycle IDs generated"


# ---------------------------------------------------------------------------
# ensure_feature_dir
# ---------------------------------------------------------------------------

class TestEnsureContainerDir:
    def test_creates_directory(self, tmp_path):
        from cycle_schema import ensure_container_dir
        cycle_id = "20260524143022-02cd7e6e"
        result = ensure_container_dir(tmp_path, cycle_id)
        assert result == tmp_path / cycle_id
        assert result.is_dir()

    def test_returns_path_to_feature_dir(self, tmp_path):
        from cycle_schema import ensure_container_dir
        cycle_id = "20260524143022-aabbccdd"
        result = ensure_container_dir(tmp_path, cycle_id)
        assert result.name == cycle_id

    def test_idempotent_if_dir_exists(self, tmp_path):
        from cycle_schema import ensure_container_dir
        cycle_id = "20260524143022-02cd7e6e"
        ensure_container_dir(tmp_path, cycle_id)
        # Second call must not raise
        result = ensure_container_dir(tmp_path, cycle_id)
        assert result.is_dir()


# ---------------------------------------------------------------------------
# update_features_json
# ---------------------------------------------------------------------------

class TestUpdateFeaturesJson:
    def test_creates_file_when_absent(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "my-feature")
        fj = tmp_path / "cycles.json"
        assert fj.exists()

    def test_initial_content_has_one_entry(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "my-feature")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data == {"20260524143022-02cd7e6e": {"name": "my-feature", "execution_mode": "guided"}}

    def test_appends_without_overwriting_existing_entry(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        (tmp_path / "cycles.json").write_text(
            json.dumps({"20260524000000-11111111": "existing-feat"})
        )
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "new-feat")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data["20260524000000-11111111"] == "existing-feat"
        assert data["20260524143022-02cd7e6e"] == {"name": "new-feat", "execution_mode": "guided"}

    def test_multiple_sequential_calls_accumulate(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        for i in range(3):
            update_cycles_json(tmp_path, f"20260524{i:06d}-abcd{i:04d}", f"feat-{i}")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert len(data) == 3

    def test_value_is_user_provided_name(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "cache restructure")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data["20260524143022-02cd7e6e"] == {"name": "cache restructure", "execution_mode": "guided"}


# ---------------------------------------------------------------------------
# main / CLI integration (subprocess)
# ---------------------------------------------------------------------------

_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


class TestCLI:
    def _run(self, tmp_path, name="test-feature", extra_args=None):
        cmd = [
            sys.executable,
            str(_CYCLE_CONTROL),
            "--project-root", str(tmp_path),
            "start",
            "--name", name,
            "--type", "feature",
        ]
        if extra_args:
            cmd.extend(extra_args)
        return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)

    def _cache_dir(self, tmp_path):
        return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"

    def test_exit_zero(self, tmp_path):
        result = self._run(tmp_path)
        assert result.returncode == 0, result.stderr

    def test_stdout_last_line_is_cycle_id(self, tmp_path):
        result = self._run(tmp_path)
        last = result.stdout.strip().splitlines()[-1]
        assert _CYCLE_ID_RE.match(last), f"Not a cycle_id: {last!r}"

    def test_feature_dir_created_under_cache(self, tmp_path):
        result = self._run(tmp_path)
        fid = result.stdout.strip().splitlines()[-1]
        assert (self._cache_dir(tmp_path) / fid).is_dir()

    def test_features_json_contains_new_entry(self, tmp_path):
        result = self._run(tmp_path, name="my-feature")
        fid = result.stdout.strip().splitlines()[-1]
        fj = self._cache_dir(tmp_path) / "cycles.json"
        data = json.loads(fj.read_text())
        assert data[fid] == {"name": "my-feature", "execution_mode": "guided"}

    def test_consecutive_calls_append_features_json(self, tmp_path):
        self._run(tmp_path, name="feat-0")
        self._run(tmp_path, name="feat-1")
        fj = self._cache_dir(tmp_path) / "cycles.json"
        data = json.loads(fj.read_text())
        assert len(data) == 2
        names = [v["name"] for v in data.values()]
        assert names == ["feat-0", "feat-1"]

    def test_invalid_project_root_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(_CYCLE_CONTROL),
             "--project-root", "/nonexistent/path/xyz", "start", "--name", "test"],
            capture_output=True, text=True, env=_ENV_COPILOT,
        )
        assert result.returncode != 0

    def test_active_session_file_not_created(self, tmp_path):
        """Regression: start must never write ACTIVE_SESSION."""
        self._run(tmp_path)
        assert not (self._cache_dir(tmp_path) / "ACTIVE_SESSION").exists()


# ---------------------------------------------------------------------------
# update_features_json — mode parameter (new behavior)
# ---------------------------------------------------------------------------

class TestUpdateFeaturesJsonMode:
    def test_default_writes_object_with_guided(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "my-feature")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data["20260524143022-02cd7e6e"] == {"name": "my-feature", "execution_mode": "guided"}

    def test_explicit_copilot_writes_object(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "my-feature", "guided")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data["20260524143022-02cd7e6e"] == {"name": "my-feature", "execution_mode": "guided"}

    def test_autonomous_writes_object(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "my-feature", "autonomous")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data["20260524143022-02cd7e6e"] == {"name": "my-feature", "execution_mode": "autonomous"}

    def test_old_slug_entries_preserved(self, tmp_path):
        """Old slug entries must not be modified (no migration)."""
        from cycle_schema import append_cycle as update_cycles_json
        (tmp_path / "cycles.json").write_text(
            json.dumps(
                {
                    "20260524000000-11111111": {
                        "name": "legacy-assisted",
                        "execution_mode": "assisted",
                    },
                    "20260524000000-22222222": {
                        "name": "legacy-self-service",
                        "execution_mode": "self-service",
                    },
                }
            )
        )
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "new-feat")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data["20260524000000-11111111"] == {
            "name": "legacy-assisted",
            "execution_mode": "assisted",
        }
        assert data["20260524000000-22222222"] == {
            "name": "legacy-self-service",
            "execution_mode": "self-service",
        }
        assert data["20260524143022-02cd7e6e"] == {
            "name": "new-feat",
            "execution_mode": "guided",
        }


# ---------------------------------------------------------------------------
# CLI — --mode flag (new behavior)
# ---------------------------------------------------------------------------

class TestCLIMode:
    def _run(self, tmp_path, name="test-feature", extra_args=None):
        cmd = [
            sys.executable,
            str(_CYCLE_CONTROL),
            "--project-root", str(tmp_path),
            "start",
            "--name", name,
            "--type", "feature",
        ]
        if extra_args:
            cmd.extend(extra_args)
        return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)

    def _cache_dir(self, tmp_path):
        return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"

    def test_no_mode_flag_writes_copilot_object(self, tmp_path):
        result = self._run(tmp_path, name="my-feature")
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert data[fid] == {"name": "my-feature", "execution_mode": "guided"}

    def test_mode_copilot_writes_object(self, tmp_path):
        result = self._run(tmp_path, name="my-feature", extra_args=["--mode", "guided"])
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert data[fid] == {"name": "my-feature", "execution_mode": "guided"}

    def test_mode_autonomous_writes_object(self, tmp_path):
        result = self._run(tmp_path, name="my-feature", extra_args=["--mode", "autonomous"])
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert data[fid] == {"name": "my-feature", "execution_mode": "autonomous"}

    def test_invalid_mode_exits_nonzero(self, tmp_path):
        result = self._run(tmp_path, name="my-feature", extra_args=["--mode", "invalid_mode"])
        assert result.returncode != 0

    def test_old_mode_assisted_exits_nonzero(self, tmp_path):
        result = self._run(tmp_path, name="my-feature", extra_args=["--mode", "assisted"])
        assert result.returncode != 0

    def test_old_mode_self_service_exits_nonzero(self, tmp_path):
        result = self._run(tmp_path, name="my-feature", extra_args=["--mode", "self-service"])
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# t3: generate_topic_id
# ---------------------------------------------------------------------------

_TOPIC_ID_RE = re.compile(r"^topic-\d{14}-[0-9a-f]{8}$")


class TestGenerateTopicId:
    def test_format_matches_pattern(self):
        from cycle_schema import generate_cycle_id
        tid = generate_cycle_id("topic")
        assert _TOPIC_ID_RE.match(tid), f"Bad format: {tid!r}"

    def test_prefix_is_topic(self):
        from cycle_schema import generate_cycle_id
        tid = generate_cycle_id("topic")
        assert tid.startswith("topic-")

    def test_consecutive_calls_unique(self):
        from cycle_schema import generate_cycle_id
        ids = [generate_cycle_id("topic") for _ in range(10)]
        assert len(set(ids)) == 10, "Duplicate topic IDs"


# ---------------------------------------------------------------------------
# t3: ensure_container_dir
# ---------------------------------------------------------------------------

class TestEnsureContainerDir:
    def test_creates_directory(self, tmp_path):
        from cycle_schema import ensure_container_dir
        cid = "topic-20260524143022-aabbccdd"
        result = ensure_container_dir(tmp_path, cid)
        assert result == tmp_path / cid
        assert result.is_dir()

    def test_idempotent(self, tmp_path):
        from cycle_schema import ensure_container_dir
        cid = "topic-20260524143022-aabbccdd"
        ensure_container_dir(tmp_path, cid)
        result = ensure_container_dir(tmp_path, cid)
        assert result.is_dir()


# ---------------------------------------------------------------------------
# t3: update_cycles_json
# ---------------------------------------------------------------------------

class TestUpdateTopicsJson:
    def test_creates_file_when_absent(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "topic-20260524143022-aabbccdd", "my-topic")
        tj = tmp_path / "cycles.json"
        assert tj.exists()

    def test_initial_content(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        tid = "topic-20260524143022-aabbccdd"
        update_cycles_json(tmp_path, tid, "my-topic")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data == {tid: {"name": "my-topic", "execution_mode": "guided"}}

    def test_mode_autonomous(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        tid = "topic-20260524143022-aabbccdd"
        update_cycles_json(tmp_path, tid, "my-topic", "autonomous")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data[tid]["execution_mode"] == "autonomous"

    def test_two_consecutive_calls_independent(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        tid1 = "topic-20260524143022-aabbccdd"
        tid2 = "topic-20260524143022-11223344"
        update_cycles_json(tmp_path, tid1, "topic-one")
        update_cycles_json(tmp_path, tid2, "topic-two")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert len(data) == 2
        assert tid1 in data
        assert tid2 in data

    def test_old_entries_unchanged(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        existing = {"topic-20260524000000-oldentry": {"name": "old", "execution_mode": "guided"}}
        (tmp_path / "cycles.json").write_text(json.dumps(existing))
        tid = "topic-20260524143022-aabbccdd"
        update_cycles_json(tmp_path, tid, "new-topic")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert data["topic-20260524000000-oldentry"] == {"name": "old", "execution_mode": "guided"}
        assert tid in data


# ---------------------------------------------------------------------------
# t3: validate_cycle_exists
# ---------------------------------------------------------------------------

class TestValidateTopicExists:
    def test_returns_true_when_exists(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json, cycle_exists as validate_cycle_exists
        tid = "topic-20260524143022-aabbccdd"
        update_cycles_json(tmp_path, tid, "my-topic")
        assert validate_cycle_exists(tmp_path, tid) is True

    def test_returns_false_when_not_exists(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json, cycle_exists as validate_cycle_exists
        tid = "topic-20260524143022-aabbccdd"
        update_cycles_json(tmp_path, tid, "my-topic")
        assert validate_cycle_exists(tmp_path, "topic-99999999999999-ffffffff") is False

    def test_returns_false_when_topics_json_absent(self, tmp_path):
        from cycle_schema import cycle_exists as validate_cycle_exists
        assert validate_cycle_exists(tmp_path, "topic-20260524143022-aabbccdd") is False


# ---------------------------------------------------------------------------
# t3: update_features_json with topic_id
# ---------------------------------------------------------------------------

class TestUpdateFeaturesJsonTopicId:
    def test_no_topic_id_arg_no_field(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "my-feature")
        data = json.loads((tmp_path / "cycles.json").read_text())
        entry = data["20260524143022-02cd7e6e"]
        assert "topic_id" not in entry

    def test_topic_id_arg_writes_field(self, tmp_path):
        from cycle_schema import append_cycle as update_cycles_json
        tid = "topic-20260524000000-aabbccdd"
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "my-feature", topic_id=tid)
        data = json.loads((tmp_path / "cycles.json").read_text())
        entry = data["20260524143022-02cd7e6e"]
        assert entry["topic_id"] == tid

    def test_old_entries_no_topic_id_unchanged(self, tmp_path):
        """Old entries lacking topic_id must not be modified when appending new entry."""
        from cycle_schema import append_cycle as update_cycles_json
        old = {"20260524000000-11111111": {"name": "old-feat", "execution_mode": "guided"}}
        (tmp_path / "cycles.json").write_text(json.dumps(old))
        update_cycles_json(tmp_path, "20260524143022-02cd7e6e", "new-feat")
        data = json.loads((tmp_path / "cycles.json").read_text())
        assert "topic_id" not in data["20260524000000-11111111"]


# ---------------------------------------------------------------------------
# t3: CLI --type topic
# ---------------------------------------------------------------------------

# _ENV_COPILOT already defined at module level above


class TestCLITypeTopic:
    def _run(self, tmp_path, name="test-topic", extra_args=None):
        cmd = [
            sys.executable, str(_CYCLE_CONTROL),
            "--project-root", str(tmp_path),
            "start",
            "--name", name,
            "--type", "topic",
        ]
        if extra_args:
            cmd.extend(extra_args)
        return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)

    def _cache_dir(self, tmp_path):
        return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"

    def test_exit_zero(self, tmp_path):
        result = self._run(tmp_path)
        assert result.returncode == 0, result.stderr

    def test_stdout_last_line_is_topic_id(self, tmp_path):
        result = self._run(tmp_path)
        last = result.stdout.strip().splitlines()[-1]
        assert _TOPIC_ID_RE.match(last), f"Not a topic_id: {last!r}"

    def test_topics_json_entry_created(self, tmp_path):
        result = self._run(tmp_path, name="my-topic")
        tid = result.stdout.strip().splitlines()[-1]
        tj = self._cache_dir(tmp_path) / "cycles.json"
        assert tj.exists()
        data = json.loads(tj.read_text())
        assert tid in data
        assert data[tid]["name"] == "my-topic"
        assert data[tid]["execution_mode"] == "guided"

    def test_topic_container_dir_created(self, tmp_path):
        result = self._run(tmp_path)
        tid = result.stdout.strip().splitlines()[-1]
        assert (self._cache_dir(tmp_path) / tid).is_dir()

    def test_two_consecutive_topics_independent(self, tmp_path):
        r1 = self._run(tmp_path, name="topic-one")
        r2 = self._run(tmp_path, name="topic-two")
        tid1 = r1.stdout.strip().splitlines()[-1]
        tid2 = r2.stdout.strip().splitlines()[-1]
        assert tid1 != tid2
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert tid1 in data
        assert tid2 in data


# ---------------------------------------------------------------------------
# t3: CLI --type feature (with and without --topic-id)
# ---------------------------------------------------------------------------

class TestCLITypeFeature:
    def _run(self, tmp_path, name="test-feature", extra_args=None):
        cmd = [
            sys.executable,
            str(_CYCLE_CONTROL),
            "--project-root", str(tmp_path),
            "start",
            "--name", name,
            "--type", "feature",
        ]
        if extra_args:
            cmd.extend(extra_args)
        return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)

    def _cache_dir(self, tmp_path):
        return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"

    def test_type_feature_exit_zero(self, tmp_path):
        result = self._run(tmp_path)
        assert result.returncode == 0, result.stderr

    def test_type_feature_stdout_is_cycle_id(self, tmp_path):
        result = self._run(tmp_path)
        last = result.stdout.strip().splitlines()[-1]
        assert _CYCLE_ID_RE.match(last), f"Not a cycle_id: {last!r}"

    def test_type_feature_no_topic_id_no_field(self, tmp_path):
        result = self._run(tmp_path, name="my-feature")
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert "topic_id" not in data[fid]

    def test_type_feature_with_valid_topic_id(self, tmp_path):
        topic_result = subprocess.run(
            [sys.executable, str(_CYCLE_CONTROL),
             "--project-root", str(tmp_path), "start", "--name", "my-topic", "--type", "topic"],
            capture_output=True, text=True, env=_ENV_COPILOT,
        )
        tid = topic_result.stdout.strip().splitlines()[-1]
        result = self._run(tmp_path, name="my-feature", extra_args=["--topic-id", tid])
        assert result.returncode == 0, result.stderr
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert data[fid]["topic_id"] == tid

    def test_type_feature_invalid_topic_id_exits_nonzero(self, tmp_path):
        result = self._run(tmp_path, name="my-feature",
                           extra_args=["--topic-id", "topic-99999999999999-ffffffff"])
        assert result.returncode != 0
        assert result.stderr.strip() != "", "stderr should have an error message"


class TestSetExecutionMode:
    def test_updates_existing_cycle(self, tmp_path):
        from cycle_schema import append_cycle, resolve_cache_dir, set_execution_mode

        cache_dir = resolve_cache_dir(tmp_path, "cursor")
        cache_dir.mkdir(parents=True)
        cycle_id = "feature-20260101000000-55555555"
        append_cycle(cache_dir, cycle_id, "demo", "guided")
        payload = set_execution_mode(cache_dir, cycle_id, "autonomous")
        assert payload == {"cycle_id": cycle_id, "execution_mode": "autonomous"}
        data = json.loads((cache_dir / "cycles.json").read_text())
        assert data[cycle_id]["execution_mode"] == "autonomous"

    def test_invalid_mode_raises(self, tmp_path):
        from cycle_schema import resolve_cache_dir, set_execution_mode

        cache_dir = resolve_cache_dir(tmp_path, "cursor")
        cache_dir.mkdir(parents=True)
        cycle_id = "feature-20260101000000-66666666"
        (cache_dir / "cycles.json").write_text(json.dumps({cycle_id: {"name": "demo", "execution_mode": "guided"}}))
        with pytest.raises(ValueError, match="invalid execution_mode"):
            set_execution_mode(cache_dir, cycle_id, "turbo")

    def test_unknown_cycle_raises(self, tmp_path):
        from cycle_schema import resolve_cache_dir, set_execution_mode

        cache_dir = resolve_cache_dir(tmp_path, "cursor")
        cache_dir.mkdir(parents=True)
        (cache_dir / "cycles.json").write_text("{}")
        with pytest.raises(ValueError, match="not found"):
            set_execution_mode(cache_dir, "feature-20260101000000-77777777", "guided")

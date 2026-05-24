#!/usr/bin/env python3
"""Tests for feature_init.py — TDD Red phase."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_FEATURE_ID_RE = re.compile(r"^\d{14}-[0-9a-f]{8}$")


# ---------------------------------------------------------------------------
# generate_feature_id
# ---------------------------------------------------------------------------

class TestGenerateFeatureId:
    def test_format_matches_pattern(self):
        from feature_init import generate_feature_id
        fid = generate_feature_id()
        assert _FEATURE_ID_RE.match(fid), f"Bad format: {fid!r}"

    def test_timestamp_part_is_14_digits(self):
        from feature_init import generate_feature_id
        fid = generate_feature_id()
        ts_part = fid.split("-")[0]
        assert len(ts_part) == 14
        assert ts_part.isdigit()

    def test_hex_part_is_8_lowercase_chars(self):
        from feature_init import generate_feature_id
        fid = generate_feature_id()
        hex_part = fid.split("-")[1]
        assert len(hex_part) == 8
        assert hex_part == hex_part.lower()
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_consecutive_calls_produce_unique_ids(self):
        from feature_init import generate_feature_id
        ids = [generate_feature_id() for _ in range(10)]
        assert len(set(ids)) == 10, "Duplicate feature IDs generated"


# ---------------------------------------------------------------------------
# ensure_feature_dir
# ---------------------------------------------------------------------------

class TestEnsureFeatureDir:
    def test_creates_directory(self, tmp_path):
        from feature_init import ensure_feature_dir
        feature_id = "20260524143022-02cd7e6e"
        result = ensure_feature_dir(tmp_path, feature_id)
        assert result == tmp_path / feature_id
        assert result.is_dir()

    def test_returns_path_to_feature_dir(self, tmp_path):
        from feature_init import ensure_feature_dir
        feature_id = "20260524143022-aabbccdd"
        result = ensure_feature_dir(tmp_path, feature_id)
        assert result.name == feature_id

    def test_idempotent_if_dir_exists(self, tmp_path):
        from feature_init import ensure_feature_dir
        feature_id = "20260524143022-02cd7e6e"
        ensure_feature_dir(tmp_path, feature_id)
        # Second call must not raise
        result = ensure_feature_dir(tmp_path, feature_id)
        assert result.is_dir()


# ---------------------------------------------------------------------------
# update_features_json
# ---------------------------------------------------------------------------

class TestUpdateFeaturesJson:
    def test_creates_file_when_absent(self, tmp_path):
        from feature_init import update_features_json
        update_features_json(tmp_path, "20260524143022-02cd7e6e", "my-feature")
        fj = tmp_path / "features.json"
        assert fj.exists()

    def test_initial_content_has_one_entry(self, tmp_path):
        from feature_init import update_features_json
        update_features_json(tmp_path, "20260524143022-02cd7e6e", "my-feature")
        data = json.loads((tmp_path / "features.json").read_text())
        assert data == {"20260524143022-02cd7e6e": "my-feature"}

    def test_appends_without_overwriting_existing_entry(self, tmp_path):
        from feature_init import update_features_json
        (tmp_path / "features.json").write_text(
            json.dumps({"20260524000000-11111111": "existing-feat"})
        )
        update_features_json(tmp_path, "20260524143022-02cd7e6e", "new-feat")
        data = json.loads((tmp_path / "features.json").read_text())
        assert data["20260524000000-11111111"] == "existing-feat"
        assert data["20260524143022-02cd7e6e"] == "new-feat"

    def test_multiple_sequential_calls_accumulate(self, tmp_path):
        from feature_init import update_features_json
        for i in range(3):
            update_features_json(tmp_path, f"20260524{i:06d}-abcd{i:04d}", f"feat-{i}")
        data = json.loads((tmp_path / "features.json").read_text())
        assert len(data) == 3

    def test_value_is_user_provided_name(self, tmp_path):
        from feature_init import update_features_json
        update_features_json(tmp_path, "20260524143022-02cd7e6e", "cache restructure")
        data = json.loads((tmp_path / "features.json").read_text())
        assert data["20260524143022-02cd7e6e"] == "cache restructure"


# ---------------------------------------------------------------------------
# main / CLI integration (subprocess)
# ---------------------------------------------------------------------------

_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


class TestCLI:
    def _run(self, tmp_path, name="test-feature", extra_args=None):
        cmd = [
            sys.executable,
            str(_SCRIPTS / "feature_init.py"),
            "--project-root", str(tmp_path),
            "--name", name,
        ]
        if extra_args:
            cmd.extend(extra_args)
        return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)

    def _cache_dir(self, tmp_path):
        return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"

    def test_exit_zero(self, tmp_path):
        result = self._run(tmp_path)
        assert result.returncode == 0, result.stderr

    def test_stdout_last_line_is_feature_id(self, tmp_path):
        result = self._run(tmp_path)
        last = result.stdout.strip().splitlines()[-1]
        assert _FEATURE_ID_RE.match(last), f"Not a feature_id: {last!r}"

    def test_feature_dir_created_under_cache(self, tmp_path):
        result = self._run(tmp_path)
        fid = result.stdout.strip().splitlines()[-1]
        assert (self._cache_dir(tmp_path) / fid).is_dir()

    def test_features_json_contains_new_entry(self, tmp_path):
        result = self._run(tmp_path, name="my-feature")
        fid = result.stdout.strip().splitlines()[-1]
        fj = self._cache_dir(tmp_path) / "features.json"
        data = json.loads(fj.read_text())
        assert data[fid] == "my-feature"

    def test_consecutive_calls_append_features_json(self, tmp_path):
        self._run(tmp_path, name="feat-0")
        self._run(tmp_path, name="feat-1")
        fj = self._cache_dir(tmp_path) / "features.json"
        data = json.loads(fj.read_text())
        assert len(data) == 2
        names = list(data.values())
        assert names == ["feat-0", "feat-1"]

    def test_invalid_project_root_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "feature_init.py"),
             "--project-root", "/nonexistent/path/xyz", "--name", "test"],
            capture_output=True, text=True, env=_ENV_COPILOT,
        )
        assert result.returncode != 0

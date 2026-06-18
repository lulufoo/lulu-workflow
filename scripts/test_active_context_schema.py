#!/usr/bin/env python3
"""Tests for active_context_schema.py — conversation-indexed active-context."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_FID = "20260601141338-3764ab2b"


def _cache_dir(tmp_path: Path, platform: str = "cursor") -> Path:
    return tmp_path / ".cache" / platform / "lulu-dev-workflow"


def _ctx_file(tmp_path: Path, platform: str = "cursor") -> Path:
    return _cache_dir(tmp_path, platform) / "active-context.json"


class TestContextPath:
    def test_cursor_platform(self, tmp_path):
        from active_context_schema import context_path

        p = context_path(tmp_path, "cursor")
        assert p == _ctx_file(tmp_path, "cursor")

    def test_copilot_platform(self, tmp_path):
        from active_context_schema import context_path

        p = context_path(tmp_path, "copilot")
        assert p == _ctx_file(tmp_path, "copilot")

    def test_claude_platform(self, tmp_path):
        from active_context_schema import context_path

        p = context_path(tmp_path, "claude")
        assert p == _ctx_file(tmp_path, "claude")

    def test_unknown_platform_fallback_cursor(self, tmp_path):
        from active_context_schema import context_path

        p = context_path(tmp_path, "codex")
        assert p == _ctx_file(tmp_path, "cursor")


class TestIsLegacyFlat:
    def test_flat_dict_is_legacy(self):
        from active_context_schema import is_legacy_flat

        assert is_legacy_flat({"cycle_id": "x", "stage": "tech-plan"}) is True

    def test_conv_indexed_is_not_legacy(self):
        from active_context_schema import is_legacy_flat

        data = {"conv-a": {"cycle_id": "x", "stage": "tech-plan"}}
        assert is_legacy_flat(data) is False

    def test_non_dict_is_not_legacy(self):
        from active_context_schema import is_legacy_flat

        assert is_legacy_flat([]) is False
        assert is_legacy_flat(None) is False


class TestReadAll:
    def test_missing_file_returns_empty(self, tmp_path):
        from active_context_schema import read_all

        assert read_all(tmp_path, "cursor") == {}

    def test_invalid_json_returns_empty(self, tmp_path):
        from active_context_schema import read_all

        path = _ctx_file(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert read_all(tmp_path, "cursor") == {}

    def test_legacy_flat_returns_empty(self, tmp_path):
        from active_context_schema import read_all

        path = _ctx_file(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"cycle_id": "x", "stage": "tech-plan"}),
            encoding="utf-8",
        )
        assert read_all(tmp_path, "cursor") == {}

    def test_filters_invalid_stage(self, tmp_path):
        from active_context_schema import read_all

        path = _ctx_file(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "good": {"cycle_id": _FID, "stage": "tech-plan"},
                    "bad": {"cycle_id": _FID, "stage": "unknown-stage"},
                }
            ),
            encoding="utf-8",
        )
        data = read_all(tmp_path, "cursor")
        assert "good" in data
        assert "bad" not in data


class TestGetEntry:
    def test_empty_conv_id_returns_none(self, tmp_path):
        from active_context_schema import get_entry

        assert get_entry(tmp_path, "cursor", "") is None

    def test_missing_conv_returns_none(self, tmp_path):
        from active_context_schema import get_entry

        assert get_entry(tmp_path, "cursor", "no-such-conv") is None


class TestWriteEntry:
    def test_write_and_read_single_entry(self, tmp_path):
        from active_context_schema import read_all, write_entry

        write_entry(tmp_path, "cursor", "conv-a", _FID, "tech-plan")
        data = read_all(tmp_path, "cursor")
        assert data["conv-a"] == {"cycle_id": _FID, "stage": "tech-plan", "cycle_type": "feature"}

    def test_merge_write_preserves_other_keys(self, tmp_path):
        from active_context_schema import read_all, write_entry

        write_entry(tmp_path, "cursor", "conv-a", _FID, "tech-plan")
        write_entry(tmp_path, "cursor", "conv-b", "other-fid", "product-plan")
        data = read_all(tmp_path, "cursor")
        assert data["conv-a"]["cycle_id"] == _FID
        assert data["conv-b"]["cycle_id"] == "other-fid"

    def test_legacy_overwritten_on_write(self, tmp_path):
        from active_context_schema import read_all, write_entry

        path = _ctx_file(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"cycle_id": "old", "stage": "tech-plan"}),
            encoding="utf-8",
        )
        write_entry(tmp_path, "cursor", "conv-new", _FID, "tech-diagnostic")
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert "cycle_id" not in raw
        assert raw["conv-new"]["stage"] == "tech-diagnostic"

    def test_write_tech_design_stage(self, tmp_path):
        from active_context_schema import read_all, write_entry

        write_entry(tmp_path, "cursor", "conv-a", _FID, "tech-design")
        data = read_all(tmp_path, "cursor")
        assert data["conv-a"] == {
            "cycle_id": _FID,
            "stage": "tech-design",
            "cycle_type": "feature",
        }

    def test_topic_rejects_tech_work_order(self, tmp_path):
        from active_context_schema import write_entry

        with pytest.raises(ValueError, match="Unknown stage"):
            write_entry(
                tmp_path,
                "cursor",
                "conv-a",
                "topic-20260101000000-aabbccdd",
                "tech-work-order",
                cycle_type="topic",
            )

    def test_feature_allows_tech_work_order(self, tmp_path):
        from active_context_schema import read_all, write_entry

        write_entry(
            tmp_path,
            "cursor",
            "conv-a",
            _FID,
            "tech-work-order",
            cycle_type="feature",
        )
        data = read_all(tmp_path, "cursor")
        assert data["conv-a"]["stage"] == "tech-work-order"

    def test_read_filters_topic_invalid_stage(self, tmp_path):
        from active_context_schema import read_all

        path = _ctx_file(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "conv-a": {
                        "cycle_id": "topic-20260101000000-aabbccdd",
                        "stage": "tech-work-order",
                        "cycle_type": "topic",
                    }
                }
            ),
            encoding="utf-8",
        )
        assert read_all(tmp_path, "cursor") == {}

    def test_diagnostic_legacy_allowed(self, tmp_path):
        from active_context_schema import read_all, write_entry

        write_entry(
            tmp_path,
            "cursor",
            "conv-a",
            _FID,
            "diagnostic",
            cycle_type="feature",
        )
        data = read_all(tmp_path, "cursor")
        assert data["conv-a"]["stage"] == "diagnostic"

    def test_invalid_stage_raises(self, tmp_path):
        from active_context_schema import write_entry

        with pytest.raises(ValueError):
            write_entry(tmp_path, "cursor", "conv-a", _FID, "not-a-stage")

    def test_empty_conv_id_no_op(self, tmp_path, capsys):
        from active_context_schema import write_entry

        write_entry(tmp_path, "cursor", "", _FID, "tech-plan")
        assert not _ctx_file(tmp_path).exists()
        err = capsys.readouterr().err
        assert "conversation_id" in err


class TestResolveConversationId:
    def test_cli_value_stripped(self):
        from active_context_schema import resolve_conversation_id

        assert resolve_conversation_id("  abc  ") == "abc"

    def test_env_fallback(self, monkeypatch):
        from active_context_schema import resolve_conversation_id

        monkeypatch.delenv("LULU_CONVERSATION_ID", raising=False)
        monkeypatch.setenv("LULU_CONVERSATION_ID", "env-conv")
        assert resolve_conversation_id(None) == "env-conv"
        assert resolve_conversation_id("") == "env-conv"

    def test_empty_returns_none(self, monkeypatch):
        from active_context_schema import resolve_conversation_id

        monkeypatch.delenv("LULU_CONVERSATION_ID", raising=False)
        assert resolve_conversation_id(None) is None
        assert resolve_conversation_id("") is None

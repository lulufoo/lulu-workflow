#!/usr/bin/env python3
"""Tests for topic-digest (cycle_schema.build_topic_digest + cycle_control CLI)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_CYCLE_CONTROL = _SCRIPTS / "cycle_control.py"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-workflow"


def _write_cycles(cache_dir: Path, data: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cycles.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_delivered_ref(
    cache_dir: Path,
    topic_id: str,
    ref_stage: str,
    body: str,
) -> Path:
    doc_dir = cache_dir / topic_id / ref_stage / "revision1"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_path = doc_dir / "doc.md"
    doc_path.write_text(body, encoding="utf-8")
    refs_path = cache_dir / topic_id / "delivered-refs.json"
    refs_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    ref_stage: {
                        "delivered_type": ref_stage,
                        "path": str(doc_path.resolve()),
                        "revision": 1,
                        "profile_id": ref_stage,
                        "delivered_at": "2026-01-01T00:00:00+00:00",
                        "source_workflow_state": "Delivered",
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return doc_path


class TestTopicDocStageFor:
    def test_mapped_stages(self):
        from transition_table import topic_doc_stage_for

        assert topic_doc_stage_for("lulu-approach") == "lulu-arch"
        assert topic_doc_stage_for("lulu-bet") == "lulu-blueprint"

    def test_unmapped_stage(self):
        from transition_table import topic_doc_stage_for

        assert topic_doc_stage_for("lulu-plan") is None


class TestBuildTopicDigest:
    def test_unmapped_stage_applicable_false(self, tmp_path):
        from cycle_schema import build_topic_digest

        cache = _cache_dir(tmp_path)
        _write_cycles(cache, {})
        payload = build_topic_digest(cache, "lulu-plan")
        assert payload == {
            "applicable": False,
            "stage": "lulu-plan",
            "ref_stage": None,
            "topics": [],
        }

    def test_filters_undelivered_and_features(self, tmp_path):
        from cycle_schema import build_topic_digest

        cache = _cache_dir(tmp_path)
        topic_ok = "topic-20260101000000-aabbccdd"
        topic_miss = "topic-20260101000001-bbccddee"
        feature_id = "feature-20260101000002-ccddeeff"
        _write_cycles(
            cache,
            {
                topic_ok: {"name": "auth-topic"},
                topic_miss: {"name": "no-arch-yet"},
                feature_id: {"name": "some-feature"},
            },
        )
        body = "# Auth Arch\n\n" + ("x" * 50)
        _write_delivered_ref(cache, topic_ok, "lulu-arch", body)

        payload = build_topic_digest(cache, "lulu-approach")
        assert payload["applicable"] is True
        assert payload["ref_stage"] == "lulu-arch"
        assert len(payload["topics"]) == 1
        item = payload["topics"][0]
        assert item["topic_id"] == topic_ok
        assert item["name"] == "auth-topic"
        assert item["ref_stage"] == "lulu-arch"
        assert "Auth Arch" in item["excerpt"]
        assert Path(item["doc_path"]).is_file()

    def test_excerpt_truncated(self, tmp_path):
        from cycle_schema import _EXCERPT_MAX_CHARS, build_topic_digest

        cache = _cache_dir(tmp_path)
        topic_id = "topic-20260101000000-aabbccdd"
        _write_cycles(cache, {topic_id: {"name": "long-doc"}})
        _write_delivered_ref(cache, topic_id, "lulu-arch", "A" * (_EXCERPT_MAX_CHARS + 200))

        payload = build_topic_digest(cache, "lulu-approach")
        assert len(payload["topics"][0]["excerpt"]) <= _EXCERPT_MAX_CHARS

    def test_lulu_bet_uses_blueprint(self, tmp_path):
        from cycle_schema import build_topic_digest

        cache = _cache_dir(tmp_path)
        topic_id = "topic-20260101000000-aabbccdd"
        _write_cycles(cache, {topic_id: {"name": "product-topic"}})
        _write_delivered_ref(cache, topic_id, "lulu-blueprint", "# Product\n\nblueprint body")

        payload = build_topic_digest(cache, "lulu-bet")
        assert payload["applicable"] is True
        assert payload["ref_stage"] == "lulu-blueprint"
        assert len(payload["topics"]) == 1
        assert "blueprint body" in payload["topics"][0]["excerpt"]


class TestCLITopicDigest:
    def _run(self, tmp_path: Path, stage: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(_CYCLE_CONTROL),
                "--project-root",
                str(tmp_path),
                "topic-digest",
                "--stage",
                stage,
            ],
            capture_output=True,
            text=True,
            env=_ENV_COPILOT,
        )

    def test_cli_applicable_false(self, tmp_path):
        result = self._run(tmp_path, "lulu-exec")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["applicable"] is False
        assert payload["topics"] == []

    def test_cli_with_delivered_topic(self, tmp_path):
        cache = _cache_dir(tmp_path)
        topic_id = "topic-20260101000000-aabbccdd"
        _write_cycles(cache, {topic_id: {"name": "cli-topic"}})
        _write_delivered_ref(cache, topic_id, "lulu-arch", "# CLI\n\nhello")

        result = self._run(tmp_path, "lulu-approach")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["applicable"] is True
        assert payload["topics"][0]["topic_id"] == topic_id
        assert "hello" in payload["topics"][0]["excerpt"]

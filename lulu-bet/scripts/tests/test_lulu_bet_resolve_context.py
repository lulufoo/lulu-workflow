#!/usr/bin/env python3
"""Tests for lulu-bet's own context resolver script.

Proves the resolution (topic) happens here, driven by lulu-bet's real
constraints-*.json templates — decision is never involved in this test.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_MODULE_PATH = _SCRIPTS / "resolve_context.py"
_spec = importlib.util.spec_from_file_location("_lulu_bet_resolve_context", _MODULE_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
resolve = _module.resolve

from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402

_TEMPLATE_FEATURE = _SCRIPTS.parent / "constraints-feature.json"
_TEMPLATE_TOPIC = _SCRIPTS.parent / "constraints-topic.json"


def _write_cycles_json(cache_dir: Path, cycle_id: str, meta: dict) -> None:
    cj = cache_dir / "cycles.json"
    data = json.loads(cj.read_text()) if cj.exists() else {}
    data[cycle_id] = meta
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj.write_text(json.dumps(data), encoding="utf-8")


def _write_topic_delivered_ref(cache_dir: Path, topic_id: str, stage: str) -> Path:
    doc_dir = cache_dir / topic_id / stage / "revision1"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc = doc_dir / f"{stage}-doc.md"
    doc.write_text("# topic doc\n", encoding="utf-8")
    refs_path = cache_dir / topic_id / "delivered-refs.json"
    refs_path.write_text(
        json.dumps({
            "version": 1,
            "entries": {
                stage: {
                    "delivered_type": stage,
                    "path": str(doc.resolve()),
                    "revision": 1,
                    "profile_id": stage,
                    "delivered_at": "2026-06-01T00:00:00+00:00",
                    "source_workflow_state": "",
                },
            },
        }),
        encoding="utf-8",
    )
    return doc


def test_feature_template_resolves_topic(tmp_path):
    """lulu-bet(feature): topic lulu-blueprint resolves via topic_id."""
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    topic_id = "topic-20260101000000-aabbccdd"
    _write_cycles_json(cache_dir, "feature-a", {"name": "x", "execution_mode": "guided", "topic_id": topic_id})
    _write_cycles_json(cache_dir, topic_id, {"name": "t", "execution_mode": "guided"})
    topic_doc = _write_topic_delivered_ref(cache_dir, topic_id, "lulu-blueprint")

    payload = resolve(tmp_path, "feature-a", _TEMPLATE_FEATURE)
    sources = payload["context"]["sources"]
    assert len(sources) == 1
    assert sources[0]["kind"] == "topic"
    assert sources[0]["status"] == "loaded"
    assert sources[0]["resolved_doc_path"] == str(topic_doc.resolve())


def test_feature_template_topic_not_found_without_topic_id(tmp_path):
    payload = resolve(tmp_path, "feature-a", _TEMPLATE_FEATURE)
    sources = payload["context"]["sources"]
    assert sources[0]["status"] == "not_found"


def test_topic_template_has_no_context(tmp_path):
    """lulu-bet(topic): top of the chain — no upstream, no cross-cycle topic source."""
    payload = resolve(tmp_path, "topic-a", _TEMPLATE_TOPIC)
    assert payload["context"] == {"status": "skipped"}


def test_cli_writes_resolved_context_file_and_prints_its_path(tmp_path):
    """decision must never receive raw JSON on the command line — the CLI
    writes the resolved context to a file and prints only that file's path,
    which lulu-bet's SKILL.md then forwards to $DEC_START via
    --domain-constraints-file."""
    result = subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--project-root",
            str(tmp_path),
            "--cycle-id",
            "feature-a",
            "--constraints",
            str(_TEMPLATE_FEATURE),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    printed_path = Path(result.stdout.strip())
    assert printed_path.is_file()
    assert printed_path.name == "resolved-context.json"
    payload = json.loads(printed_path.read_text(encoding="utf-8"))
    assert payload["context"]["sources"][0]["kind"] == "topic"


def test_write_resolved_context_returns_path_next_to_session_cache_subdir(tmp_path):
    write_resolved_context = _module.write_resolved_context
    path = write_resolved_context(tmp_path, "feature-a", _TEMPLATE_FEATURE)
    assert path.is_file()
    assert path.parent.name == "lulu-bet"
    assert path.parent.parent.name == "feature-a"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "context" in payload

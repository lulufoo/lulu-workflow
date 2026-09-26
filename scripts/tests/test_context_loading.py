#!/usr/bin/env python3
"""Tests for context_loading.build_context_loading — flat context.docs map."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import context_loading  # noqa: E402
from context_loading import build_context_loading  # noqa: E402


def _make_upstream_doc(cache_dir: Path, cycle_id: str, subdir: str, doc_filename: str) -> Path:
    rev_dir = cache_dir / cycle_id / subdir / "revision1"
    rev_dir.mkdir(parents=True, exist_ok=True)
    (rev_dir / "workflow-state.md").write_text(
        "---\ncurrent_state: Delivered\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    doc = rev_dir / doc_filename
    doc.write_text("# doc\n", encoding="utf-8")
    return doc


def _write_cycles_json(cache_dir: Path, cycle_id: str, meta: dict) -> None:
    cj = cache_dir / "cycles.json"
    data = json.loads(cj.read_text()) if cj.exists() else {}
    data[cycle_id] = meta
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj.write_text(json.dumps(data), encoding="utf-8")


def _write_topic_delivered_ref(cache_dir: Path, topic_id: str, ref_stage: str) -> Path:
    doc_dir = cache_dir / topic_id / ref_stage / "revision1"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc = doc_dir / f"{ref_stage}-doc.md"
    doc.write_text("# topic doc\n", encoding="utf-8")
    refs_path = cache_dir / topic_id / "delivered-refs.json"
    refs_path.write_text(
        json.dumps({
            "version": 1,
            "entries": {
                ref_stage: {
                    "delivered_type": ref_stage,
                    "path": str(doc.resolve()),
                    "revision": 1,
                    "profile_id": ref_stage,
                    "delivered_at": "2026-06-01T00:00:00+00:00",
                    "source_workflow_state": "",
                },
            },
        }),
        encoding="utf-8",
    )
    return doc


def test_lulu_bet_topic_cycle_empty_docs(tmp_path):
    result = build_context_loading("topic-a", "lulu-bet", cache_dir=tmp_path)
    assert result == {"docs": {}}


def test_lulu_bet_feature_cycle_topic_blueprint_loaded(tmp_path):
    topic_id = "topic-20260101000000-aabbccdd"
    _write_cycles_json(tmp_path, "feature-a", {"name": "x", "topic_id": topic_id})
    _write_cycles_json(tmp_path, topic_id, {"name": "t"})
    doc = _write_topic_delivered_ref(tmp_path, topic_id, "lulu-blueprint")

    result = build_context_loading("feature-a", "lulu-bet", cache_dir=tmp_path)
    assert result["docs"] == {
        "product_blueprint": str(doc.resolve()),
    }


def test_lulu_bet_feature_cycle_omits_missing_topic(tmp_path):
    _write_cycles_json(tmp_path, "feature-a", {"name": "x"})
    result = build_context_loading("feature-a", "lulu-bet", cache_dir=tmp_path)
    assert result == {"docs": {}}


def test_lulu_approach_feature_cycle_product_spec_and_tech_arch(tmp_path):
    topic_id = "topic-20260101000000-aabbccdd"
    _write_cycles_json(tmp_path, "feature-a", {"name": "x", "topic_id": topic_id})
    _write_cycles_json(tmp_path, topic_id, {"name": "t"})
    upstream_doc = _make_upstream_doc(tmp_path, "feature-a", "lulu-spec", "product-doc.md")
    topic_doc = _write_topic_delivered_ref(tmp_path, topic_id, "lulu-arch")

    result = build_context_loading("feature-a", "lulu-approach", cache_dir=tmp_path)
    assert result["docs"]["product_spec"] == upstream_doc.resolve().as_posix()
    assert result["docs"]["tech_arch"] == str(topic_doc.resolve())


def test_lulu_approach_feature_cycle_omits_undelivered_upstream(tmp_path):
    _write_cycles_json(tmp_path, "feature-a", {"name": "x"})
    result = build_context_loading("feature-a", "lulu-approach", cache_dir=tmp_path)
    assert "product_spec" not in result["docs"]


def test_lulu_approach_topic_cycle_blueprint_only(tmp_path):
    doc = _make_upstream_doc(tmp_path, "topic-a", "lulu-blueprint", "product-doc.md")
    result = build_context_loading("topic-a", "lulu-approach", cache_dir=tmp_path)
    assert result["docs"] == {
        "product_blueprint": doc.resolve().as_posix(),
    }


def test_predecessor_stage_returns_none_for_entry_point():
    assert context_loading._predecessor_stage("feature", "lulu-bet") is None


def test_predecessor_stage_resolves_single_non_null_edge():
    assert context_loading._predecessor_stage("feature", "lulu-approach") == "lulu-spec"


def test_predecessor_stage_raises_on_ambiguous_edges(tmp_path, monkeypatch):
    table = {
        "version": 2,
        "feature": [
            {"from": None, "to": ["x"]},
            {"from": "a", "to": ["x"]},
            {"from": "b", "to": ["x"]},
        ],
    }
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "transition-table.json").write_text(json.dumps(table), encoding="utf-8")
    monkeypatch.setattr(context_loading, "_CONFIG_DIR", config_dir)
    try:
        context_loading._predecessor_stage("feature", "x")
    except ValueError as exc:
        assert "ambiguous predecessor" in str(exc)
    else:
        raise AssertionError("expected ValueError for ambiguous predecessor")

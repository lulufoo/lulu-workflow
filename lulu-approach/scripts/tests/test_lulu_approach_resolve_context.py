#!/usr/bin/env python3
"""Tests for lulu-approach's context resolver (flat docs + Dx parent keys)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_MODULE_PATH = _SCRIPTS / "resolve_context.py"
_spec = importlib.util.spec_from_file_location("_lulu_approach_resolve_context", _MODULE_PATH)
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


def test_feature_template_resolves_product_spec_and_tech_arch(tmp_path):
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    topic_id = "topic-20260101000000-aabbccdd"
    _write_cycles_json(cache_dir, "feature-a", {"name": "x", "topic_id": topic_id})
    _write_cycles_json(cache_dir, topic_id, {"name": "t"})
    upstream_doc = _make_upstream_doc(cache_dir, "feature-a", "lulu-spec", "product-doc.md")
    topic_doc = _write_topic_delivered_ref(cache_dir, topic_id, "lulu-arch")

    payload = resolve(tmp_path, "feature-a", _TEMPLATE_FEATURE)
    docs = payload["context"]["docs"]
    assert docs["product_spec"] == upstream_doc.resolve().as_posix()
    assert docs["tech_arch"] == str(topic_doc.resolve())
    assert "main_decision" not in docs
    assert "boundary_rules" not in docs


def test_feature_template_omits_missing_docs(tmp_path):
    payload = resolve(tmp_path, "feature-a", _TEMPLATE_FEATURE)
    assert payload["context"]["docs"] == {}


def test_topic_template_resolves_blueprint_only(tmp_path):
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    upstream_doc = _make_upstream_doc(cache_dir, "topic-a", "lulu-blueprint", "product-doc.md")

    payload = resolve(tmp_path, "topic-a", _TEMPLATE_TOPIC)
    assert payload["context"]["docs"] == {
        "product_blueprint": upstream_doc.resolve().as_posix(),
    }


def test_dx_requires_main_decision_doc(tmp_path):
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    approach = cache_dir / "feature-a" / "lulu-approach"
    (approach / "main").mkdir(parents=True)
    dx = approach / "D1"
    dx.mkdir()
    try:
        resolve(tmp_path, "feature-a", _TEMPLATE_FEATURE, session_dir=dx)
    except ValueError as exc:
        assert "main decision doc missing" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_dx_adds_main_decision_boundary_rules_and_optional_split(tmp_path):
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    approach = cache_dir / "feature-a" / "lulu-approach"
    main = approach / "main"
    main.mkdir(parents=True)
    main_doc = main / "decision-doc.md"
    main_doc.write_text("# main\n", encoding="utf-8")
    pkg = approach / "decision-package.json"
    pkg.write_text("{}", encoding="utf-8")
    dx = approach / "D1"
    dx.mkdir()

    payload = resolve(tmp_path, "feature-a", _TEMPLATE_FEATURE, session_dir=dx)
    docs = payload["context"]["docs"]
    assert docs["main_decision"] == main_doc.resolve().as_posix()
    assert docs["decision_split"] == pkg.resolve().as_posix()
    boundary = (_SCRIPTS.parent / "references" / "boundary-rules.md").resolve()
    assert docs["boundary_rules"] == boundary.as_posix()
    assert boundary.is_file()


def test_dx_requires_boundary_rules_file(tmp_path, monkeypatch):
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    approach = cache_dir / "feature-a" / "lulu-approach"
    main = approach / "main"
    main.mkdir(parents=True)
    (main / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    dx = approach / "D1"
    dx.mkdir()
    missing = tmp_path / "missing-boundary-rules.md"
    monkeypatch.setattr(_module, "_BOUNDARY_RULES_PATH", missing)
    try:
        resolve(tmp_path, "feature-a", _TEMPLATE_FEATURE, session_dir=dx)
    except ValueError as exc:
        assert "boundary rules missing" in str(exc)
    else:
        raise AssertionError("expected ValueError")

def test_cli_writes_resolved_context_file_and_prints_its_path(tmp_path):
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
    assert "docs" in payload["context"]


def test_write_resolved_context_returns_path_next_to_session_cache_subdir(tmp_path):
    write_resolved_context = _module.write_resolved_context
    path = write_resolved_context(tmp_path, "feature-a", _TEMPLATE_FEATURE)
    assert path.is_file()
    assert path.parent.name == "lulu-approach"
    assert path.parent.parent.name == "feature-a"


def test_write_resolved_context_binding_id_under_bindings(tmp_path):
    write_resolved_context = _module.write_resolved_context
    path = write_resolved_context(
        tmp_path,
        "feature-a",
        _TEMPLATE_FEATURE,
        binding_id="bind-abc123",
    )
    assert path.is_file()
    assert path.as_posix().endswith("bindings/bind-abc123/resolved-context.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "docs" in payload["context"]

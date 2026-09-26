#!/usr/bin/env python3
"""Tests for Context / Constraint material resolvers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_CONTEXT_CLI = _SCRIPTS / "resolve_context_docs.py"
_CONSTRAINT_CLI = _SCRIPTS / "resolve_constraint_docs.py"
_MAT_PATH = _SCRIPTS / "material_docs.py"
_spec = importlib.util.spec_from_file_location("_material_docs", _MAT_PATH)
_mat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mat)
resolve_material_files = _mat.resolve_material_files

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


def test_resolve_context_and_constraint_files(tmp_path):
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    topic_id = "topic-20260101000000-aabbccdd"
    _write_cycles_json(cache_dir, "feature-a", {"name": "x", "topic_id": topic_id})
    _write_cycles_json(cache_dir, topic_id, {"name": "t"})
    upstream = _make_upstream_doc(cache_dir, "feature-a", "lulu-spec", "product-doc.md")
    arch = _write_topic_delivered_ref(cache_dir, topic_id, "lulu-arch")

    ctx = resolve_material_files(tmp_path, "feature-a", _TEMPLATE_FEATURE, "context")
    cons = resolve_material_files(tmp_path, "feature-a", _TEMPLATE_FEATURE, "constraint")
    assert ctx == [upstream.resolve().as_posix()]
    assert cons == [str(arch.resolve())]


def test_resolve_material_files_empty_when_missing(tmp_path):
    assert resolve_material_files(tmp_path, "feature-a", _TEMPLATE_FEATURE, "context") == []
    assert resolve_material_files(tmp_path, "feature-a", _TEMPLATE_FEATURE, "constraint") == []


def test_topic_context_includes_product_blueprint(tmp_path):
    cache_dir = tmp_path / platform_cache_dir(detect_platform())
    upstream = _make_upstream_doc(cache_dir, "topic-a", "lulu-blueprint", "product-doc.md")
    files = resolve_material_files(tmp_path, "topic-a", _TEMPLATE_TOPIC, "context")
    assert files == [upstream.resolve().as_posix()]


def test_cli_context_docs_stdout_json(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(_CONTEXT_CLI),
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
    payload = json.loads(result.stdout)
    assert payload == {"files": []}


def test_cli_constraint_docs_stdout_json(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(_CONSTRAINT_CLI),
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
    payload = json.loads(result.stdout)
    assert payload == {"files": []}

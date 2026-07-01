#!/usr/bin/env python3
"""Tests for profile-driven eval WorkflowAdapter loading (eval_entry.py)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_entry  # noqa: E402


def _write_adapter_module(workflow_root: Path) -> Path:
    adapter_dir = workflow_root / "tech-foo" / "scripts" / "eval"
    adapter_dir.mkdir(parents=True)
    adapter_path = adapter_dir / "tech_foo_eval_adapter.py"
    adapter_path.write_text(
        "\n".join(
            [
                "class TechFooEvalAdapter:",
                "    marker = 'loaded-from-profile'",
            ],
        ),
        encoding="utf-8",
    )
    return adapter_path


def _write_profile(workflow_root: Path, *, adapter_class: str = "TechFooEvalAdapter") -> Path:
    profile_dir = workflow_root / "tech-foo"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "compose-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "profile_id": "tech-foo",
                "eval": {
                    "adapter_module": "tech-foo/scripts/eval/tech_foo_eval_adapter.py",
                    "adapter_class": adapter_class,
                },
            },
        ),
        encoding="utf-8",
    )
    return profile_path


def test_load_eval_adapter_from_profile_path(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root)
    profile_path = _write_profile(workflow_root)

    adapter = eval_entry.load_eval_adapter(
        {
            "eval": {
                "adapter_module": "tech-foo/scripts/eval/tech_foo_eval_adapter.py",
                "adapter_class": "TechFooEvalAdapter",
            },
        },
        profile_path,
    )

    assert adapter.marker == "loaded-from-profile"


def test_load_eval_adapter_reports_missing_class(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root)
    profile_path = _write_profile(workflow_root, adapter_class="MissingAdapter")

    try:
        eval_entry.load_eval_adapter(
            {
                "eval": {
                    "adapter_module": "tech-foo/scripts/eval/tech_foo_eval_adapter.py",
                    "adapter_class": "MissingAdapter",
                },
            },
            profile_path,
        )
    except ValueError as exc:
        assert "adapter class 'MissingAdapter' not found" in str(exc)
    else:
        raise AssertionError("expected missing adapter class to fail")


def test_load_eval_adapter_requires_adapter_module() -> None:
    try:
        eval_entry.load_eval_adapter({"eval": {}}, Path("/tmp/tech-foo/compose-profile.json"))
    except ValueError as exc:
        assert "profile.eval.adapter_module is required" in str(exc)
    else:
        raise AssertionError("expected missing adapter_module to fail")


def test_main_loads_profile_adapter_before_run_eval(tmp_path: Path, monkeypatch) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root)
    profile_path = _write_profile(workflow_root)
    args = argparse.Namespace(workflow="tech-foo", cycle_id="C1", project_root=tmp_path)
    captured = {}

    monkeypatch.setattr(eval_entry, "parse_args", lambda: args)
    monkeypatch.setattr(eval_entry, "compose_profile_path", lambda _profile_id: profile_path)

    def fake_run_eval(parsed_args, adapter):
        captured["args"] = parsed_args
        captured["adapter"] = adapter
        return 23

    monkeypatch.setattr(eval_entry, "run_eval", fake_run_eval)

    assert eval_entry.main() == 23
    assert captured["args"] is args
    assert captured["adapter"].marker == "loaded-from-profile"


def test_main_rejects_profile_id_mismatch(tmp_path: Path, monkeypatch) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root)
    profile_path = _write_profile(workflow_root)
    args = argparse.Namespace(workflow="other-stage", cycle_id="C1", project_root=tmp_path)

    monkeypatch.setattr(eval_entry, "parse_args", lambda: args)
    monkeypatch.setattr(eval_entry, "compose_profile_path", lambda _profile_id: profile_path)

    assert eval_entry.main() == 1

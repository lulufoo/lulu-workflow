#!/usr/bin/env python3
"""Tests for profile-driven StartAdapter loading."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bootstrap  # noqa: F401
import start  # noqa: E402


def _write_adapter_module(workflow_root: Path) -> Path:
    adapter_dir = workflow_root / "tech-foo" / "scripts" / "start"
    adapter_dir.mkdir(parents=True)
    adapter_path = adapter_dir / "tech_foo_start_adapter.py"
    adapter_path.write_text(
        "\n".join(
            [
                "class TechFooStartAdapter:",
                "    marker = 'loaded-from-profile'",
                "",
                "    def validate_for_start(self, *args, **kwargs):",
                "        return []",
                "",
                "    def infer_run_mode(self, *args, **kwargs):",
                "        return 'tech'",
                "",
                "    def resolve_delivered_refs(self, *args, **kwargs):",
                "        return []",
                "",
                "    def resolve_scope_refs(self, *args, **kwargs):",
                "        return []",
                "",
                "    def post_start_guidance(self, *args, **kwargs):",
                "        return ''",
                "",
                "    def delivered_ref_for_init(self, *args, **kwargs):",
                "        return None",
            ],
        ),
        encoding="utf-8",
    )
    return adapter_path


def _write_profile(workflow_root: Path, *, adapter_class: str = "TechFooStartAdapter") -> Path:
    profile_dir = workflow_root / "tech-foo"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "compose-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "profile_id": "tech-foo",
                "start": {
                    "adapter_module": "tech-foo/scripts/start/tech_foo_start_adapter.py",
                    "adapter_class": adapter_class,
                },
            },
        ),
        encoding="utf-8",
    )
    return profile_path


def test_load_start_adapter_from_profile_path(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root)
    profile_path = _write_profile(workflow_root)

    adapter = start.load_start_adapter(
        {
            "start": {
                "adapter_module": "tech-foo/scripts/start/tech_foo_start_adapter.py",
                "adapter_class": "TechFooStartAdapter",
            },
        },
        profile_path,
    )

    assert adapter.marker == "loaded-from-profile"


def test_load_start_adapter_reports_missing_class(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root)
    profile_path = _write_profile(workflow_root, adapter_class="MissingAdapter")

    try:
        start.load_start_adapter(
            {
                "start": {
                    "adapter_module": "tech-foo/scripts/start/tech_foo_start_adapter.py",
                    "adapter_class": "MissingAdapter",
                },
            },
            profile_path,
        )
    except ValueError as exc:
        assert "adapter class 'MissingAdapter' not found" in str(exc)
    else:
        raise AssertionError("expected missing adapter class to fail")


def test_main_loads_profile_adapter_before_run_start(tmp_path: Path, monkeypatch) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root)
    profile_path = _write_profile(workflow_root)
    args = argparse.Namespace(profile="tech-foo", profile_path=profile_path.as_posix())
    captured = {}

    monkeypatch.setattr(start, "parse_args", lambda: args)
    monkeypatch.setattr(start, "validate_compose_profile_path", lambda *_args: None)
    monkeypatch.setattr(
        start,
        "read_profile_for_start",
        lambda *_args: json.loads(profile_path.read_text(encoding="utf-8")),
    )

    def fake_run_start(parsed_args, adapter):
        captured["args"] = parsed_args
        captured["adapter"] = adapter
        return 23

    monkeypatch.setattr(start, "run_start", fake_run_start)

    assert start.main() == 23
    assert captured["args"] is args
    assert captured["adapter"].marker == "loaded-from-profile"

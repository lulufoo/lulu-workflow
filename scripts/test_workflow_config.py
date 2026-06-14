#!/usr/bin/env python3
"""Tests for workflow_config_schema.py and workflow_config.py CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from workflow_config_schema import (  # noqa: E402
    apply_workflow_config_from_url,
    resolve_workflow_config_path,
)

_DEFAULT_URL = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/template/workflow-config.json"
)


class TestConfigureWorkflowConfig:
    def test_writes_to_resolved_skill_config_path(self, tmp_path: Path) -> None:
        payload = {"version": 1, "tech-plan": {"ptc_url": "https://example.com/ptc.md"}}

        def stub_fetch(owner: str, repo: str, ref: str, path: str) -> str:
            assert owner == "lulufoo"
            assert repo == "lulu-workflow-framework"
            assert ref == "main"
            assert path == "template/workflow-config.json"
            return json.dumps(payload)

        import fetch_template as ft

        original = ft.gh_api_fetch
        ft.gh_api_fetch = stub_fetch
        try:
            target = apply_workflow_config_from_url(
                tmp_path,
                _DEFAULT_URL,
                platform="cursor",
            )
        finally:
            ft.gh_api_fetch = original

        expected = resolve_workflow_config_path(tmp_path, "cursor")
        assert target == expected
        written = json.loads(expected.read_text(encoding="utf-8"))
        assert written == payload

    def test_cli_configure_prints_path(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "fetch_template.gh_api_fetch",
            lambda owner, repo, ref, path: json.dumps({"version": 1}),
        )
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "workflow_config.py"),
                "configure",
                "--project-root",
                str(tmp_path),
                "--platform",
                "cursor",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip().endswith("skill-config/lulu-dev-workflow/workflow-config.json")

    def test_cli_resolve_path(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "workflow_config.py"),
                "resolve-path",
                "--project-root",
                str(tmp_path),
                "--platform",
                "cursor",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip().endswith("skill-config/lulu-dev-workflow/workflow-config.json")

    def test_invalid_json_raises(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "fetch_template.gh_api_fetch",
            lambda *_args: "not-json",
        )
        with pytest.raises(ValueError, match="not valid JSON"):
            apply_workflow_config_from_url(tmp_path, _DEFAULT_URL, platform="cursor")

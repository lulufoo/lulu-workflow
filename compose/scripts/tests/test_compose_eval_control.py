#!/usr/bin/env python3
"""Tests for Compose Eval adapter-config passthrough."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_CORE = Path(__file__).resolve().parents[1] / "eval"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import compose_eval_control  # noqa: E402
from compose_eval_control import extract_eval_adapter_config  # noqa: E402
from workflow_paths import seed_profile_pointer_for_tests  # noqa: E402


def test_extract_builds_decorator_envelope() -> None:
    profile = {
        "profile_id": "lulu-design",
        "eval": {
            "enabled": True,
            "workflow_id": "lulu-design",
            "contributor_module": "lulu-design/scripts/eval/tech_design_eval_contributor.py",
            "contributor_class": "TechDesignEvalContributor",
            "eval_capability": "full-remediation",
        },
    }
    config = extract_eval_adapter_config(profile)
    assert config["adapter_class"] == "ComposeEvalAdapter"
    assert config["construction"] == "decorator"
    assert config["adapter_options"]["delegate"]["class"] == "TechDesignEvalContributor"
    assert config["workflow_id"] == "lulu-design"
    assert config["enabled"] is True
    assert config["profile_digest"]


def test_extract_requires_contributor_fields() -> None:
    with pytest.raises(ValueError, match="contributor_module"):
        extract_eval_adapter_config({"eval": {"enabled": True}})


def test_real_design_profile_has_eval_block() -> None:
    profile_path = (
        Path(__file__).resolve().parents[3]
        / "lulu-design"
        / "compose-profile.json"
    )
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    config = extract_eval_adapter_config(profile)
    assert config["adapter_class"] == "ComposeEvalAdapter"
    assert config["adapter_options"]["delegate"]["class"] == "TechDesignEvalContributor"


def test_main_forwards_full_round_completion_to_eval_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _run(command: list[str], *, check: bool) -> SimpleNamespace:
        captured["command"] = command
        captured["config"] = json.loads(
            Path(command[command.index("--adapter-config-file") + 1]).read_text(
                encoding="utf-8",
            ),
        )
        assert check is False
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(compose_eval_control.subprocess, "run", _run)

    seed_profile_pointer_for_tests(tmp_path, "compose-full-round", "lulu-design")
    result = compose_eval_control.main(
        [
            "--cycle-id",
            "compose-full-round",
            "--project-root",
            str(tmp_path),
            "--",
            "remediation-complete",
        ],
    )

    assert result == 0
    assert captured["command"][-1] == "remediation-complete"
    assert captured["config"]["workflow_id"] == "lulu-design"


def test_skill_style_help_resolves_workflow_paths() -> None:
    """SKILL invokes this file directly; pytest bootstrap must not hide import gaps."""
    script = Path(__file__).resolve().parents[1] / "eval" / "compose_eval_control.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--cycle-id" in completed.stdout

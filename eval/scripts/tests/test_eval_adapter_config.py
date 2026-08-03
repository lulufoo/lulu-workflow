#!/usr/bin/env python3
"""Tests for caller-supplied Eval adapter config loading."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_adapter_config as eac
import eval_entry


def _write_adapter_module(workflow_root: Path, content: str) -> Path:
    adapter_dir = workflow_root / "non-compose" / "scripts" / "eval"
    adapter_dir.mkdir(parents=True)
    adapter_path = adapter_dir / "non_compose_eval_adapter.py"
    adapter_path.write_text(content, encoding="utf-8")
    return adapter_path


def test_loads_adapter_from_config_file(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(
        workflow_root,
        "class NonComposeEvalAdapter:\n    marker = 'loaded-from-config'\n",
    )
    config_path = tmp_path / "adapter.json"
    config_path.write_text(
        json.dumps(
            {
                "workflow_id": "non-compose",
                "adapter_module": (
                    "non-compose/scripts/eval/non_compose_eval_adapter.py"
                ),
                "adapter_class": "NonComposeEvalAdapter",
            }
        ),
        encoding="utf-8",
    )

    adapter = eac.load_eval_adapter_from_config(
        config_path,
        workflow_root=workflow_root,
    )
    assert adapter.marker == "loaded-from-config"


def test_rejects_missing_adapter_class(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root, "class PresentAdapter:\n    pass\n")
    with pytest.raises(ValueError, match="adapter class 'MissingAdapter' not found"):
        eac.load_eval_adapter_from_config(
            {
                "adapter_module": (
                    "non-compose/scripts/eval/non_compose_eval_adapter.py"
                ),
                "adapter_class": "MissingAdapter",
            },
            workflow_root=workflow_root,
        )


def test_rejects_path_traversal(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    workflow_root.mkdir()
    with pytest.raises(ValueError, match="path traversal"):
        eac.load_eval_adapter_from_config(
            {
                "adapter_module": "../outside_adapter.py",
                "adapter_class": "OutsideAdapter",
            },
            workflow_root=workflow_root,
        )


def test_rejects_enabled_false() -> None:
    with pytest.raises(ValueError, match="enabled is false"):
        eac.validate_adapter_config(
            {
                "adapter_module": "x.py",
                "adapter_class": "X",
                "enabled": False,
            }
        )


def test_entry_loads_config_before_handoff(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    config_path.write_text(
        json.dumps(
            {
                "workflow_id": "non-compose",
                "adapter_module": "unused.py",
                "adapter_class": "Unused",
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeAdapter:
        def request_eval_handoff(self, **kwargs):
            captured["handoff_args"] = kwargs
            return {"version": 2, "context": {}}

    def fake_run_eval(parsed_args, adapter, *, handoff):
        captured["workflow"] = parsed_args.workflow
        captured["adapter"] = adapter
        captured["handoff"] = handoff
        return 23

    fake_adapter = FakeAdapter()
    monkeypatch.setattr(
        eval_entry,
        "load_adapter_config_file",
        lambda path: eac.validate_adapter_config(
            {
                "workflow_id": "non-compose",
                "adapter_module": "m.py",
                "adapter_class": "C",
            }
        ),
    )
    monkeypatch.setattr(
        eval_entry,
        "load_eval_adapter_from_config",
        lambda config: fake_adapter,
    )
    monkeypatch.setattr(eval_entry, "run_eval", fake_run_eval)

    code = eval_entry.main(
        [
            "--adapter-config-file",
            str(config_path),
            "--cycle-id",
            "C1",
            "--project-root",
            str(tmp_path),
            "begin-eval-round",
        ]
    )
    assert code == 23
    assert captured["workflow"] == "non-compose"
    assert captured["adapter"] is fake_adapter
    assert captured["handoff_args"] == {
        "cycle_id": "C1",
        "project_root": tmp_path.resolve(),
        "require_evaluating": False,
    }


def test_entry_requires_adapter_config(tmp_path: Path) -> None:
    code = eval_entry.main(
        [
            "--cycle-id",
            "C1",
            "--project-root",
            str(tmp_path),
            "begin-eval-round",
        ]
    )
    assert code == 1

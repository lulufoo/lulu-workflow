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
                "eval_capability": "full-remediation",
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
                "eval_capability": "full-remediation",
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
                "eval_capability": "full-remediation",
            },
            workflow_root=workflow_root,
        )


def test_rejects_enabled_false() -> None:
    with pytest.raises(ValueError, match="enabled is false"):
        eac.validate_adapter_config(
            {
                "adapter_module": "x.py",
                "adapter_class": "X",
                "eval_capability": "full-remediation",
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
                "eval_capability": "full-remediation",
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeAdapter:
        def eval_admission_context(self, *args, **kwargs):
            raise NotImplementedError

        def prepare_eval_admission(self, *args, **kwargs):
            return {"ok": False, "error": "stub"}

        def abort_eval_admission(self, *args, **kwargs):
            return {"ok": True}
        def request_eval_handoff(self, **kwargs):
            captured["handoff_args"] = kwargs
            raise AssertionError("begin-eval-round must not request handoff at entry")

        def read_eval_target_digest(self, *args, **kwargs):
            return "digest"

        def commit_eval_target(self, *args, **kwargs):
            return {"ok": True}

        def restore_eval_target(self, *args, **kwargs):
            return {"ok": True}

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
                "eval_capability": "full-remediation",
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
    assert captured["handoff"] is None
    assert "handoff_args" not in captured


def test_loads_decorator_adapter_and_delegate(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    adapter_dir = workflow_root / "compose" / "scripts" / "eval"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "compose_eval_adapter.py").write_text(
        (
            "class ComposeEvalAdapter:\n"
            "    def __init__(self, *, workflow_id, contributor, "
            "eval_capability='full-remediation', profile_digest=''):\n"
            "        self.workflow_id = workflow_id\n"
            "        self.contributor = contributor\n"
            "        self.eval_capability = eval_capability\n"
            "        self.profile_digest = profile_digest\n"
            "    @classmethod\n"
            "    def from_config(cls, envelope, *, contributor):\n"
            "        return cls(\n"
            "            workflow_id=envelope['workflow_id'],\n"
            "            contributor=contributor,\n"
            "            eval_capability=envelope['eval_capability'],\n"
            "            profile_digest=envelope.get('profile_digest', ''),\n"
            "        )\n"
        ),
        encoding="utf-8",
    )
    delegate_dir = workflow_root / "lulu-design" / "scripts" / "eval"
    delegate_dir.mkdir(parents=True)
    (delegate_dir / "tech_design_eval_contributor.py").write_text(
        "class TechDesignEvalContributor:\n"
        "    marker = 'delegate-loaded'\n"
        "    def contribute(self, *, context):\n"
        "        return context\n",
        encoding="utf-8",
    )

    adapter = eac.load_eval_adapter_from_config(
        {
            "adapter_module": "compose/scripts/eval/compose_eval_adapter.py",
            "adapter_class": "ComposeEvalAdapter",
            "workflow_id": "lulu-design",
            "eval_capability": "full-remediation",
            "construction": "decorator",
            "profile_digest": "abc",
            "adapter_options": {
                "delegate": {
                    "module": "lulu-design/scripts/eval/tech_design_eval_contributor.py",
                    "class": "TechDesignEvalContributor",
                }
            },
        },
        workflow_root=workflow_root,
    )
    assert adapter.workflow_id == "lulu-design"
    assert adapter.contributor.marker == "delegate-loaded"
    assert adapter.profile_digest == "abc"


def test_decorator_rejects_delegate_traversal(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    adapter_dir = workflow_root / "compose" / "scripts" / "eval"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "compose_eval_adapter.py").write_text(
        "class ComposeEvalAdapter:\n    @classmethod\n"
        "    def from_config(cls, envelope, *, contributor):\n"
        "        return cls()\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="path traversal"):
        eac.load_eval_adapter_from_config(
            {
                "adapter_module": "compose/scripts/eval/compose_eval_adapter.py",
                "adapter_class": "ComposeEvalAdapter",
                "eval_capability": "full-remediation",
                "construction": "decorator",
                "adapter_options": {
                    "delegate": {
                        "module": "../outside.py",
                        "class": "Outside",
                    }
                },
            },
            workflow_root=workflow_root,
        )


def test_flat_rejects_delegate() -> None:
    with pytest.raises(ValueError, match="must not include adapter_options.delegate"):
        eac.validate_adapter_config(
            {
                "adapter_module": "x.py",
                "adapter_class": "X",
                "eval_capability": "full-remediation",
                "adapter_options": {"delegate": {"module": "y.py", "class": "Y"}},
            }
        )


def test_missing_construction_is_flat() -> None:
    config = eac.validate_adapter_config(
        {
            "adapter_module": "x.py",
            "adapter_class": "X",
            "eval_capability": "full-remediation",
        }
    )
    assert config.construction == "flat"


def test_loads_real_design_decorator_envelope() -> None:
    workflow_root = Path(__file__).resolve().parents[3]
    profile = json.loads(
        (workflow_root / "lulu-design" / "compose-profile.json").read_text(
            encoding="utf-8"
        )
    )
    sys.path.insert(0, str(workflow_root / "compose" / "scripts" / "eval"))
    from compose_eval_envelope import build_compose_eval_envelope

    envelope = build_compose_eval_envelope(profile)
    adapter = eac.load_eval_adapter_from_config(envelope, workflow_root=workflow_root)
    assert adapter.WORKFLOW_ID == "lulu-design"
    assert callable(adapter._contributor.contribute)


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

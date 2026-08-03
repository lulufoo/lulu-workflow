#!/usr/bin/env python3
"""Tests for the generic eval adapter registry seam."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_adapter_registry
import eval_entry


def _write_adapter_module(workflow_root: Path, content: str) -> Path:
    adapter_dir = workflow_root / "non-compose" / "scripts" / "eval"
    adapter_dir.mkdir(parents=True)
    adapter_path = adapter_dir / "non_compose_eval_adapter.py"
    adapter_path.write_text(content, encoding="utf-8")
    return adapter_path


def _write_registry(workflow_root: Path, workflows: list[dict[str, str]]) -> Path:
    registry_path = workflow_root / "eval" / "adapter-registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps({"workflows": workflows}), encoding="utf-8")
    return registry_path


def test_loads_registered_non_compose_adapter(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(
        workflow_root,
        "class NonComposeEvalAdapter:\n    marker = 'loaded-from-registry'\n",
    )
    registry_path = _write_registry(
        workflow_root,
        [
            {
                "id": "non-compose",
                "adapter_module": (
                    "non-compose/scripts/eval/non_compose_eval_adapter.py"
                ),
                "adapter_class": "NonComposeEvalAdapter",
            },
        ],
    )

    adapter = eval_adapter_registry.load_eval_adapter(
        "non-compose",
        registry_path=registry_path,
        workflow_root=workflow_root,
    )

    assert adapter.marker == "loaded-from-registry"


def test_rejects_missing_adapter_class(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    _write_adapter_module(workflow_root, "class PresentAdapter:\n    pass\n")
    registry_path = _write_registry(
        workflow_root,
        [
            {
                "id": "non-compose",
                "adapter_module": (
                    "non-compose/scripts/eval/non_compose_eval_adapter.py"
                ),
                "adapter_class": "MissingAdapter",
            },
        ],
    )

    with pytest.raises(ValueError, match="adapter class 'MissingAdapter' not found"):
        eval_adapter_registry.load_eval_adapter(
            "non-compose",
            registry_path=registry_path,
            workflow_root=workflow_root,
        )


def test_rejects_unknown_workflow(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    registry_path = _write_registry(
        workflow_root,
        [
            {
                "id": "registered",
                "adapter_module": "registered.py",
                "adapter_class": "RegisteredAdapter",
            },
        ],
    )

    with pytest.raises(ValueError, match="unknown eval workflow: missing"):
        eval_adapter_registry.load_eval_adapter(
            "missing",
            registry_path=registry_path,
            workflow_root=workflow_root,
        )


def test_rejects_adapter_path_escape(tmp_path: Path) -> None:
    workflow_root = tmp_path / "lulu-dev-workflow"
    registry_path = _write_registry(
        workflow_root,
        [
            {
                "id": "non-compose",
                "adapter_module": "../outside_adapter.py",
                "adapter_class": "OutsideAdapter",
            },
        ],
    )

    with pytest.raises(ValueError, match="adapter_module contains path traversal"):
        eval_adapter_registry.load_eval_adapter(
            "non-compose",
            registry_path=registry_path,
            workflow_root=workflow_root,
        )


def test_rejects_duplicate_workflow_ids() -> None:
    with pytest.raises(ValueError, match="duplicate workflow id: non-compose"):
        eval_adapter_registry.validate_adapter_registry(
            {
                "workflows": [
                    {
                        "id": "non-compose",
                        "adapter_module": "one.py",
                        "adapter_class": "OneAdapter",
                    },
                    {
                        "id": "non-compose",
                        "adapter_module": "two.py",
                        "adapter_class": "TwoAdapter",
                    },
                ],
            },
        )


def test_loads_builtin_registry_metadata_without_importing_adapters() -> None:
    registrations = eval_adapter_registry.load_adapter_registry()

    assert {
        workflow_id: (
            registration.adapter_class,
            registration.adapter_module,
        )
        for workflow_id, registration in registrations.items()
    } == {
        "lulu-design": (
            "TechDesignEvalAdapter",
            "lulu-design/scripts/eval/tech_design_eval_adapter.py",
        ),
        "lulu-plan": (
            "TechPlanEvalAdapter",
            "lulu-plan/scripts/eval/tech_plan_eval_adapter.py",
        ),
        "lulu-arch": (
            "TechArchEvalAdapter",
            "lulu-arch/scripts/eval/tech_arch_eval_adapter.py",
        ),
        "lulu-spec": (
            "ProductSpecEvalAdapter",
            "lulu-spec/scripts/eval/product_spec_eval_adapter.py",
        ),
        "lulu-blueprint": (
            "ProductBlueprintEvalAdapter",
            "lulu-blueprint/scripts/eval/product_blueprint_eval_adapter.py",
        ),
        "lulu-decision": (
            "DecisionEvalAdapter",
            "decision/scripts/eval/decision_eval_adapter.py",
        ),
    }


def test_entry_loads_registered_adapter_before_requesting_handoff(monkeypatch, tmp_path: Path) -> None:
    args = argparse.Namespace(
        workflow="non-compose",
        cycle_id="C1",
        project_root=tmp_path,
        command="begin-eval-round",
    )
    captured: dict[str, object] = {}

    class FakeAdapter:
        def request_eval_handoff(self, **kwargs):
            captured["handoff_args"] = kwargs
            return {"adapter": {}, "context": {}}

    def fake_run_eval(parsed_args, adapter, *, handoff):
        captured["args"] = parsed_args
        captured["adapter"] = adapter
        captured["handoff"] = handoff
        return 23

    fake_adapter = FakeAdapter()
    monkeypatch.setattr(eval_entry, "parse_args", lambda: args)
    monkeypatch.setattr(eval_entry, "load_eval_adapter", lambda workflow_id: (
        fake_adapter if workflow_id == "non-compose" else None
    ))
    monkeypatch.setattr(eval_entry, "run_eval", fake_run_eval)

    assert eval_entry.main() == 23
    assert captured["adapter"] is fake_adapter
    assert captured["handoff_args"] == {
        "cycle_id": "C1",
        "project_root": tmp_path,
        "require_evaluating": False,
    }

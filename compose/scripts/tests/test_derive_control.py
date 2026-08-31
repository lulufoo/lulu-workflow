#!/usr/bin/env python3
"""CLI / control tests for derive_control.py (K1 mechanical shell, Step 3 — Derive facts).

Uses in-process cmd_* calls so ``_graph_and_maps`` can be monkeypatched
(subprocess cannot see the patch).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_DEDUCTIVE = Path(__file__).resolve().parent.parent / "deductive"
_KERNEL = Path(__file__).resolve().parent.parent / "_kernel"
sys.path.insert(0, str(_KERNEL))
sys.path.insert(0, str(_DEDUCTIVE))

import derive_control as mod  # noqa: E402
from workflow_paths import seed_revision_profile_pointer  # noqa: E402

_PLANISH_GRAPH = {
    "sections": {
        "AR": {"upstream": [], "relations": {}},
        "SK": {"upstream": ["AR"], "relations": {"AR": "operationalize"}},
        "T": {
            "upstream": ["SK", "AR"],
            "relations": {"SK": "decompose", "AR": "instantiate"},
        },
        "GO": {"upstream": [], "relations": {}},
        "ZZ": {"upstream": [], "relations": {}},
    },
}
_ORDER = ["AR", "SK", "T", "GO", "ZZ"]
_PRESENCE = {
    "AR": "required",
    "SK": "required",
    "T": "required",
    "GO": "optional",
    "ZZ": "required",
}


def _seed_facts(rev: Path, facts: list[dict]) -> None:
    rev.mkdir(parents=True, exist_ok=True)
    seed_revision_profile_pointer(rev)
    slice_dir = rev / "L1"
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "_facts.json").write_text(
        json.dumps(facts, ensure_ascii=False),
        encoding="utf-8",
    )


def _patch_graph(monkeypatch) -> None:
    def stub_graph_and_maps(project_root, profile_id, **_kwargs):  # noqa: ARG001
        return _PLANISH_GRAPH, _ORDER, _PRESENCE

    monkeypatch.setattr(mod, "_graph_and_maps", stub_graph_and_maps)
    monkeypatch.setattr(
        mod,
        "_load_registry",
        lambda root, pid, **_k: {"section_order": _ORDER},  # noqa: ARG005
    )


def test_cli_append_and_audit_round_trip(tmp_path: Path, monkeypatch, capsys) -> None:
    _patch_graph(monkeypatch)
    rev = tmp_path / "revision1"
    step2_facts = [
        {"id": "F-1", "text": "ar", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "sk", "lens_tags": ["SK"]},
    ]
    _seed_facts(rev, step2_facts)
    before = tmp_path / "before-facts.json"
    before.write_text(json.dumps(step2_facts), encoding="utf-8")
    derived = tmp_path / "derived.json"
    derived.write_text(
        json.dumps(
            [
                {
                    "text": "task from sk",
                    "lens_tags": ["T"],
                    "source": ["F-2"],
                },
            ],
        ),
        encoding="utf-8",
    )

    assert (
        mod.cmd_append(
            argparse.Namespace(
                revision_dir=rev,
                derived_file=derived,
                project_root=tmp_path,
            ),
        )
        == 0
    )
    ap = json.loads(capsys.readouterr().out)
    assert ap["appended"] == 1
    assert ap["facts_after"] == 3
    on_disk = json.loads((rev / "L1" / "_facts.json").read_text(encoding="utf-8"))
    assert on_disk[2]["id"] == "F-3"
    assert on_disk[2]["source"] == ["F-2"]

    assert (
        mod.cmd_audit(
            argparse.Namespace(
                revision_dir=rev,
                before_file=before,
                triggered="T",
                project_root=tmp_path,
            ),
        )
        == 0
    )

    # Silent T after cascade SK append → audit fails
    cascade_rev = tmp_path / "revision2"
    cascade_before = [{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}]
    cascade_after = cascade_before + [
        {
            "id": "F-2",
            "text": "sk derived",
            "lens_tags": ["SK"],
            "source": ["F-1"],
        },
    ]
    _seed_facts(cascade_rev, cascade_after)
    before2 = tmp_path / "cascade-before.json"
    before2.write_text(json.dumps(cascade_before), encoding="utf-8")

    cascade_graph = {
        "sections": {
            "AR": {"upstream": [], "relations": {}},
            "SK": {"upstream": ["AR"], "relations": {"AR": "decompose"}},
            "T": {"upstream": ["SK"], "relations": {"SK": "decompose"}},
        },
    }

    def stub_cascade(project_root, profile_id, **_kwargs):  # noqa: ARG001
        return (
            cascade_graph,
            ["AR", "SK", "T"],
            {"AR": "required", "SK": "required", "T": "required"},
        )

    monkeypatch.setattr(mod, "_graph_and_maps", stub_cascade)
    assert (
        mod.cmd_audit(
            argparse.Namespace(
                revision_dir=cascade_rev,
                before_file=before2,
                triggered="SK,T",
                project_root=tmp_path,
            ),
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "T" in err


def test_cmd_audit_empty_triggered_is_noop_success(tmp_path: Path, capsys) -> None:
    rev = tmp_path / "rev-empty"
    before_facts = [{"id": "F-1", "text": "only", "lens_tags": ["AR"]}]
    _seed_facts(rev, before_facts)
    before = tmp_path / "before.json"
    before.write_text(json.dumps(before_facts), encoding="utf-8")
    assert (
        mod.cmd_audit(
            argparse.Namespace(
                revision_dir=rev,
                before_file=before,
                triggered="",
                project_root=tmp_path,
            ),
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["triggered"] == []
    assert payload["skipped"] == "empty-triggered"


def test_cli_edge_scan_requires_fact_intake_eval_gate(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _patch_graph(monkeypatch)
    rev = tmp_path / "revision1"
    _seed_facts(
        rev,
        [
            {"id": "F-1", "text": "ar", "lens_tags": ["AR"]},
            {"id": "F-2", "text": "sk", "lens_tags": ["SK"]},
        ],
    )
    args = argparse.Namespace(
        revision_dir=rev,
        project_root=tmp_path,
    )
    assert mod.cmd_edge_scan(args) == 1
    assert "fact-intake eval gate missing" in capsys.readouterr().err

    sys.path.insert(
        0,
        str(
            Path(__file__).resolve().parents[2]
            / "fact-intake-runner"
            / "fact-intake-eval"
            / "scripts"
        ),
    )
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[3] / "eval" / "scripts")
    )
    from fact_intake_eval_runtime_schema import evaluate_state_path  # noqa: E402
    from evaluate_state_schema import (  # noqa: E402
        build_initial_evaluate_state,
        save_evaluate_state,
    )

    es_path = evaluate_state_path(rev / "L1")
    data = build_initial_evaluate_state(
        dimension_ids=["e1-doc-coverage", "e2-fact-provenance"],
        evaluate_round=1,
        focus_l="revision1",
        eval_capability="full-remediation",
        handling_policy={
            "e1-doc-coverage": "class-default",
            "e2-fact-provenance": "class-default",
        },
        corpus_digest="abc",
        corpus_snapshot_ref="corpus-snapshot/manifest.json",
    )
    data["eval_status"] = "done"
    data["eval_phase"] = "done"
    data["dimension_status"] = (
        '{"e1-doc-coverage":"complete","e2-fact-provenance":"complete"}'
    )
    save_evaluate_state(es_path, data, merge=False)
    assert mod.cmd_edge_scan(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "edge-scan"


def test_cli_classify(tmp_path: Path, monkeypatch, capsys) -> None:
    _patch_graph(monkeypatch)
    rev = tmp_path / "revision1"
    _seed_facts(
        rev,
        [
            {"id": "F-1", "text": "ar", "lens_tags": ["AR"]},
            {"id": "F-2", "text": "sk", "lens_tags": ["SK"]},
        ],
    )
    assert (
        mod.cmd_classify(
            argparse.Namespace(
                revision_dir=rev,
                project_root=tmp_path,
            ),
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["derivation"] == ["T"]
    assert payload["true_gaps"] == ["ZZ"]

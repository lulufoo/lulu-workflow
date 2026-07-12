#!/usr/bin/env python3
"""CLI / control tests for pd_control.py (K1 mechanical shell).

Uses in-process cmd_* calls so ``_graph_and_maps`` can be monkeypatched
(subprocess cannot see the patch).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

import pd_control as mod  # noqa: E402

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
    (rev / "_facts.json").write_text(
        json.dumps(facts, ensure_ascii=False),
        encoding="utf-8",
    )


def _patch_graph(monkeypatch) -> None:
    def stub_graph_and_maps(project_root, profile_id):  # noqa: ARG001
        return _PLANISH_GRAPH, _ORDER, _PRESENCE

    monkeypatch.setattr(mod, "_graph_and_maps", stub_graph_and_maps)


def test_cli_plan_triggers_and_true_gaps(tmp_path: Path, monkeypatch, capsys) -> None:
    _patch_graph(monkeypatch)
    rev = tmp_path / "rev"
    _seed_facts(
        rev,
        [
            {"id": "F-1", "text": "ar", "lens_tags": ["AR"]},
            {"id": "F-2", "text": "sk", "lens_tags": ["SK"]},
        ],
    )
    args = argparse.Namespace(
        revision_dir=rev,
        profile="lulu-plan",
        project_root=tmp_path,
    )
    assert mod.cmd_plan(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["triggered"] == ["T"]
    assert payload["order"] == ["T"]
    assert payload["true_gaps"] == ["ZZ"]
    assert "T" in payload["upstreams"]
    assert payload["upstreams"]["T"]["upstream_fact_count"] == 2


def test_cli_append_and_audit_round_trip(tmp_path: Path, monkeypatch, capsys) -> None:
    _patch_graph(monkeypatch)
    rev = tmp_path / "rev"
    p0 = [
        {"id": "F-1", "text": "ar", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "sk", "lens_tags": ["SK"]},
    ]
    _seed_facts(rev, p0)
    before = tmp_path / "p0.json"
    before.write_text(json.dumps(p0), encoding="utf-8")
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
                profile="",
                project_root=tmp_path,
            ),
        )
        == 0
    )
    ap = json.loads(capsys.readouterr().out)
    assert ap["appended"] == 1
    assert ap["facts_after"] == 3
    on_disk = json.loads((rev / "_facts.json").read_text(encoding="utf-8"))
    assert on_disk[2]["id"] == "F-3"
    assert on_disk[2]["source"] == ["F-2"]

    assert (
        mod.cmd_audit(
            argparse.Namespace(
                revision_dir=rev,
                before_file=before,
                triggered="T",
                profile="lulu-plan",
                project_root=tmp_path,
            ),
        )
        == 0
    )

    # Silent T after cascade SK append → audit fails
    cascade_rev = tmp_path / "cascade"
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

    def stub_cascade(project_root, profile_id):  # noqa: ARG001
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
                profile="lulu-plan",
                project_root=tmp_path,
            ),
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "T" in err


def test_cli_classify(tmp_path: Path, monkeypatch, capsys) -> None:
    _patch_graph(monkeypatch)
    rev = tmp_path / "rev"
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
                profile="lulu-plan",
                project_root=tmp_path,
            ),
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["derivation"] == ["T"]
    assert payload["true_gaps"] == ["ZZ"]

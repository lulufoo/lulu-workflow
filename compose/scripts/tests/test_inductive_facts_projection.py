#!/usr/bin/env python3
"""Tests for K2 inductive → _facts.json projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

_INDUCTIVE = Path(__file__).resolve().parent.parent / "inductive"
_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_INDUCTIVE))
sys.path.insert(0, str(_SECTION))

import inductive_facts_projection as proj  # noqa: E402
from facts_schema import load_facts  # noqa: E402
from pd_derivation import append_derived_facts  # noqa: E402


def _decision(
    section: str,
    n: int,
    text: str,
    *,
    intent_ref: str | None = None,
    code_refs: list | None = None,
) -> dict:
    d: dict = {
        "id": f"{section}-d{n}",
        "kw": 1,
        "text": text,
        "trigger": "human",
        "means": "direct",
        "confidence": "direct",
    }
    if intent_ref is not None:
        d["intent_ref"] = intent_ref
    if code_refs is not None:
        d["code_refs"] = code_refs
    return d


def _section(key: str, decisions: list[dict]) -> dict:
    return {
        "key": key,
        "status": "cleared",
        "frontier_kw": 2,
        "decisions": decisions,
        "open": [],
        "deferred": [],
    }


def test_project_renumbers_and_tags_1_to_1() -> None:
    facts = proj.project_decisions_to_facts(
        section_order=["CTX", "GO", "I"],
        sections_by_key={
            "CTX": _section(
                "CTX",
                [_decision("CTX", 1, "ctx-a"), _decision("CTX", 2, "ctx-b")],
            ),
            "GO": _section("GO", [_decision("GO", 1, "go-a")]),
            "I": _section("I", []),
        },
    )
    assert [f["id"] for f in facts] == ["F-1", "F-2", "F-3"]
    assert facts[0]["text"] == "ctx-a"
    assert facts[0]["lens_tags"] == ["CTX"]
    assert facts[2]["lens_tags"] == ["GO"]
    assert facts[0]["source"] == ["CTX-d1"]
    # Rich fields must not leak
    for f in facts:
        assert "kw" not in f
        assert "trigger" not in f
        assert "means" not in f
        assert "confidence" not in f


def test_project_source_packs_intent_and_code_refs() -> None:
    facts = proj.project_decisions_to_facts(
        section_order=["ST"],
        sections_by_key={
            "ST": _section(
                "ST",
                [
                    _decision(
                        "ST",
                        1,
                        "settled",
                        intent_ref="intent://x",
                        code_refs=["src/a.py:10", "src/b.py:2"],
                    )
                ],
            ),
        },
    )
    assert facts[0]["source"] == ["ST-d1", "intent://x", "src/a.py:10", "src/b.py:2"]


def test_project_empty_all_raises() -> None:
    with pytest.raises(proj.EmptyProjectionError, match="no inductive decisions"):
        proj.project_decisions_to_facts(
            section_order=["A", "B"],
            sections_by_key={
                "A": _section("A", []),
                "B": _section("B", []),
            },
        )


def test_project_skips_missing_section_file() -> None:
    facts = proj.project_decisions_to_facts(
        section_order=["A", "B"],
        sections_by_key={"B": _section("B", [_decision("B", 1, "only-b")])},
    )
    assert len(facts) == 1
    assert facts[0]["id"] == "F-1"
    assert facts[0]["lens_tags"] == ["B"]


def test_project_orphans_outside_order_hard_error() -> None:
    with pytest.raises(proj.OrphanSectionError, match="outside section_order"):
        proj.project_decisions_to_facts(
            section_order=["A"],
            sections_by_key={
                "A": _section("A", [_decision("A", 1, "in-order")]),
                "ZZ": _section("ZZ", [_decision("ZZ", 1, "orphan")]),
            },
        )


def test_project_orphan_empty_decisions_ok() -> None:
    """Orphan section with empty decisions is harmless (nothing to drop)."""
    facts = proj.project_decisions_to_facts(
        section_order=["A"],
        sections_by_key={
            "A": _section("A", [_decision("A", 1, "in-order")]),
            "ZZ": _section("ZZ", []),
        },
    )
    assert [f["id"] for f in facts] == ["F-1"]


def test_project_empty_decision_text_raises() -> None:
    with pytest.raises(ValueError, match="empty text"):
        proj.project_decisions_to_facts(
            section_order=["A"],
            sections_by_key={
                "A": _section(
                    "A",
                    [
                        {
                            "id": "A-d1",
                            "kw": 1,
                            "text": "   ",
                            "trigger": "human",
                            "means": "direct",
                            "confidence": "direct",
                        }
                    ],
                ),
            },
        )


def test_load_and_cli_project(tmp_path: Path, monkeypatch, capsys) -> None:
    rev = tmp_path / "revision1"
    indir = rev / "inductive-scope"
    indir.mkdir(parents=True)
    (indir / "CTX.json").write_text(
        json.dumps(_section("CTX", [_decision("CTX", 1, "hello")]), ensure_ascii=False),
        encoding="utf-8",
    )
    (indir / "GO.json").write_text(
        json.dumps(_section("GO", [_decision("GO", 1, "world")]), ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(proj, "_section_order", lambda *_a, **_k: ["CTX", "GO"])

    args = argparse.Namespace(
        revision_dir=rev,
        inductive_dir=None,
        profile="lulu-design",
        project_root=tmp_path,
    )
    assert proj.cmd_project(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["facts_total"] == 2

    loaded = load_facts(rev / "_facts.json")
    assert [f["id"] for f in loaded] == ["F-1", "F-2"]
    assert loaded[0]["text"] == "hello"
    assert loaded[1]["source"] == ["GO-d1"]


def test_cli_project_empty_hard_errors(tmp_path: Path, monkeypatch, capsys) -> None:
    rev = tmp_path / "revision1"
    indir = rev / "inductive-scope"
    indir.mkdir(parents=True)
    (indir / "CTX.json").write_text(
        json.dumps(_section("CTX", []), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(proj, "_section_order", lambda *_a, **_k: ["CTX"])

    args = argparse.Namespace(
        revision_dir=rev,
        inductive_dir=None,
        profile="lulu-design",
        project_root=tmp_path,
    )
    assert proj.cmd_project(args) == 1
    err = capsys.readouterr().err
    assert "no inductive decisions to project" in err
    assert not (rev / "_facts.json").exists()


def test_pd_tail_append_after_projection() -> None:
    """§3: projection sets F-1..F-m; Pd continuous tail append."""
    base = proj.project_decisions_to_facts(
        section_order=["SK", "T"],
        sections_by_key={
            "SK": _section("SK", [_decision("SK", 1, "skill fact")]),
            "T": _section("T", []),
        },
    )
    assert [f["id"] for f in base] == ["F-1"]
    after = append_derived_facts(
        base,
        [
            {
                "text": "derived task",
                "lens_tags": ["T"],
                "source": ["F-1"],
            }
        ],
    )
    assert [f["id"] for f in after] == ["F-1", "F-2"]
    assert after[1]["lens_tags"] == ["T"]
    assert after[1]["source"] == ["F-1"]


def test_reproject_overwrites_full_facts(tmp_path: Path, monkeypatch, capsys) -> None:
    rev = tmp_path / "revision1"
    indir = rev / "inductive-scope"
    indir.mkdir(parents=True)
    (indir / "A.json").write_text(
        json.dumps(_section("A", [_decision("A", 1, "first")]), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(proj, "_section_order", lambda *_a, **_k: ["A"])
    args = argparse.Namespace(
        revision_dir=rev,
        inductive_dir=None,
        profile="x",
        project_root=tmp_path,
    )
    assert proj.cmd_project(args) == 0
    capsys.readouterr()

    (indir / "A.json").write_text(
        json.dumps(
            _section(
                "A",
                [_decision("A", 1, "first"), _decision("A", 2, "second")],
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert proj.cmd_project(args) == 0
    loaded = load_facts(rev / "_facts.json")
    assert [f["text"] for f in loaded] == ["first", "second"]

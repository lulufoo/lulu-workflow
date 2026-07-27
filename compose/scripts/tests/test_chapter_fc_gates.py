#!/usr/bin/env python3
"""Tests for chapter F/C + expression_conventions provenance hard gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SECTION = Path(__file__).resolve().parents[1] / "section"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from chapter_fc_gates import (  # noqa: E402
    DOMAIN_MARKERS,
    check_chapter_write_artifacts,
    check_derive_fc,
)


def _valid_derive(**overrides: object) -> dict:
    data: dict = {
        "lens": "AR",
        "form": {"carrier": "prose", "structure": "claim-then-evidence"},
        "expression": [
            "from expression_conventions.register: precise engineering prose",
            "from expression_conventions.carriers: stay inside chosen form",
            "from expression_conventions.scannability: short items over walls",
            "from expression_conventions.altitude: act without re-deriving intent",
        ],
    }
    data.update(overrides)
    return data


def test_domain_markers_are_expression_conventions_keys():
    assert DOMAIN_MARKERS == (
        "expression_conventions.register",
        "expression_conventions.carriers",
        "expression_conventions.scannability",
        "expression_conventions.altitude",
    )


def test_check_derive_fc_passes_valid():
    assert check_derive_fc(_valid_derive()) == []


def test_legacy_domain_dot_prefix_alone_does_not_pass():
    """Brittle domain.* labels are no longer sufficient without SoT key paths."""
    errs = check_derive_fc(
        _valid_derive(
            expression=[
                "domain.register: precise engineering prose",
                "domain.carriers: follow Derive F/C",
                "domain.scannability: short items over walls",
                "domain.altitude: act without re-deriving intent",
            ],
        ),
    )
    assert any("expression_conventions.register" in e for e in errs)


def test_check_derive_fc_requires_form_carrier_and_structure():
    errs = check_derive_fc(
        _valid_derive(form={"carrier": "prose", "structure": "  "}),
    )
    assert any("form.structure" in e for e in errs)

    errs = check_derive_fc(_valid_derive(form={"carrier": "", "structure": "x"}))
    assert any("form.carrier" in e for e in errs)

    errs = check_derive_fc(_valid_derive(form="prose"))
    assert any("form" in e for e in errs)


def test_check_derive_fc_requires_nonempty_expression_list():
    assert any(
        "expression" in e for e in check_derive_fc(_valid_derive(expression=[]))
    )
    assert any(
        "expression" in e for e in check_derive_fc(_valid_derive(expression="x"))
    )


def test_check_derive_fc_requires_four_provenance_markers_in_expression():
    errs = check_derive_fc(
        _valid_derive(
            expression=[
                "from expression_conventions.register: ok",
                "from expression_conventions.carriers: ok",
                "from expression_conventions.scannability: ok",
                # missing altitude
            ],
        ),
    )
    assert any("expression_conventions.altitude" in e for e in errs)


def test_check_derive_fc_rejects_retired_expression_c_key_only():
    """Hard cut: only expression_c (no expression) fails with rename hint."""
    data = {
        "lens": "AR",
        "form": {"carrier": "prose", "structure": "claim-then-evidence"},
        "expression_c": [
            "from expression_conventions.register: precise engineering prose",
            "from expression_conventions.carriers: stay inside chosen form",
            "from expression_conventions.scannability: short items over walls",
            "from expression_conventions.altitude: act without re-deriving intent",
        ],
    }
    errs = check_derive_fc(data)
    assert any(
        "expression_c is retired; use expression for the chapter C array" in e
        for e in errs
    )
    assert any("expression must be a non-empty array" in e for e in errs)


def test_check_derive_fc_rejects_expression_c_even_when_expression_valid():
    """Hard cut: expression_c present is always an error (no dual-read)."""
    data = _valid_derive()
    data["expression_c"] = list(data["expression"])
    errs = check_derive_fc(data)
    assert any(
        "expression_c is retired; use expression for the chapter C array" in e
        for e in errs
    )


def test_check_derive_fc_does_not_require_display_title():
    data = _valid_derive()
    assert "display_title" not in data
    assert check_derive_fc(data) == []


def test_check_chapter_write_artifacts_happy(tmp_path: Path):
    cid = "A01-AR"
    (tmp_path / f"_derive-{cid}.json").write_text(
        json.dumps(_valid_derive()), encoding="utf-8",
    )
    (tmp_path / f"_body-{cid}.txt").write_text("body prose\n", encoding="utf-8")
    assert check_chapter_write_artifacts(tmp_path, cid) == []


def test_check_chapter_write_artifacts_rejects_empty_body(tmp_path: Path):
    cid = "A01-AR"
    (tmp_path / f"_derive-{cid}.json").write_text(
        json.dumps(_valid_derive()), encoding="utf-8",
    )
    (tmp_path / f"_body-{cid}.txt").write_text("  \n", encoding="utf-8")
    errs = check_chapter_write_artifacts(tmp_path, cid)
    assert any("empty body" in e for e in errs)


def test_check_chapter_write_artifacts_rejects_missing_fc(tmp_path: Path):
    cid = "A01-AR"
    (tmp_path / f"_derive-{cid}.json").write_text(
        json.dumps({"lens": "AR"}), encoding="utf-8",
    )
    (tmp_path / f"_body-{cid}.txt").write_text("body\n", encoding="utf-8")
    errs = check_chapter_write_artifacts(tmp_path, cid)
    assert any("form" in e for e in errs)
    assert any("expression" in e for e in errs)


def _write_chapter(
    tmp_path: Path,
    cid: str,
    *,
    structure: str,
    body: str,
) -> None:
    (tmp_path / f"_derive-{cid}.json").write_text(
        json.dumps(
            _valid_derive(form={"carrier": "prose", "structure": structure}),
        ),
        encoding="utf-8",
    )
    (tmp_path / f"_body-{cid}.txt").write_text(body, encoding="utf-8")


def test_body_form_structure_diagram_with_mermaid_passes(tmp_path: Path):
    """S1: catalog key diagram + mermaid opening fence → green."""
    cid = "S01-ST"
    _write_chapter(
        tmp_path,
        cid,
        structure="diagram",
        body="Intro\n\n```mermaid\nflowchart LR\n  A-->B\n```\n",
    )
    assert check_chapter_write_artifacts(tmp_path, cid) == []


def test_body_form_structure_diagram_without_mermaid_fails(tmp_path: Path):
    """S2: diagram without mermaid fence → single-template error."""
    cid = "S01-ST"
    _write_chapter(
        tmp_path,
        cid,
        structure="diagram",
        body="Just a bullet list:\n- a\n- b\n",
    )
    errs = check_chapter_write_artifacts(tmp_path, cid)
    assert len(errs) == 1
    msg = errs[0]
    assert f"{cid}: form.structure=diagram expects" in msg
    assert "```mermaid" in msg
    assert f"_body-{cid}.txt" in msg
    assert "rewrite body to match form" in msg


def test_body_form_structure_table_without_separator_fails(tmp_path: Path):
    """S3: table without markdown separator → same template shape."""
    cid = "T01-ST"
    _write_chapter(
        tmp_path,
        cid,
        structure="table",
        body="ColA ColB\nrow1 row2\n",
    )
    errs = check_chapter_write_artifacts(tmp_path, cid)
    assert len(errs) == 1
    msg = errs[0]
    assert f"{cid}: form.structure=table expects" in msg
    assert f"_body-{cid}.txt" in msg
    assert "rewrite body to match form" in msg


def test_body_form_structure_table_with_separator_passes(tmp_path: Path):
    cid = "T01-ST"
    _write_chapter(
        tmp_path,
        cid,
        structure="table",
        body="| A | B |\n| --- | --- |\n| 1 | 2 |\n",
    )
    assert check_chapter_write_artifacts(tmp_path, cid) == []


def test_body_form_structure_unknown_key_skips(tmp_path: Path):
    """S4: structure not in catalog → no probe failure."""
    cid = "A01-AR"
    _write_chapter(
        tmp_path,
        cid,
        structure="prose",
        body="plain prose without mermaid or table\n",
    )
    assert check_chapter_write_artifacts(tmp_path, cid) == []


def test_body_form_structure_first_token_lookup(tmp_path: Path):
    """Normalize: first whitespace token is the catalog key."""
    cid = "S02-ST"
    _write_chapter(
        tmp_path,
        cid,
        structure="diagram primary",
        body="no fence here\n",
    )
    errs = check_chapter_write_artifacts(tmp_path, cid)
    assert any("form.structure=diagram expects" in e for e in errs)


def test_body_form_structure_engine_has_no_per_structure_branches():
    """S6: no structure== diagram/table rule branches in the runner module."""
    src = (_SECTION / "chapter_fc_gates.py").read_text(encoding="utf-8")
    forbidden = (
        'structure == "diagram"',
        "structure == 'diagram'",
        'structure == "table"',
        "structure == 'table'",
        '== "diagram"',
        "== 'diagram'",
        '== "table"',
        "== 'table'",
    )
    for needle in forbidden:
        assert needle not in src, f"forbidden structure branch: {needle}"
    catalog = (_SECTION / "form_structure_body_probes.json").read_text(
        encoding="utf-8",
    )
    assert "```mermaid" in catalog
    assert "```mermaid" not in src

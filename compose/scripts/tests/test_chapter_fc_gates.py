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

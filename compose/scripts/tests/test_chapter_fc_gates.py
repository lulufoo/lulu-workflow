#!/usr/bin/env python3
"""Tests for chapter F/C + domain-marker hard gate (converge Q1–Q4)."""

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
        "expression_c": [
            "domain.register: precise engineering prose",
            "domain.carriers: follow Derive F/C",
            "domain.scannability: short items over walls",
            "domain.altitude: act without re-deriving intent",
        ],
    }
    data.update(overrides)
    return data


def test_domain_markers_are_the_four_prefixes():
    assert DOMAIN_MARKERS == (
        "domain.register",
        "domain.carriers",
        "domain.scannability",
        "domain.altitude",
    )


def test_check_derive_fc_passes_valid():
    assert check_derive_fc(_valid_derive()) == []


def test_check_derive_fc_requires_form_carrier_and_structure():
    errs = check_derive_fc(
        _valid_derive(form={"carrier": "prose", "structure": "  "}),
    )
    assert any("form.structure" in e for e in errs)

    errs = check_derive_fc(_valid_derive(form={"carrier": "", "structure": "x"}))
    assert any("form.carrier" in e for e in errs)

    errs = check_derive_fc(_valid_derive(form="prose"))
    assert any("form" in e for e in errs)


def test_check_derive_fc_requires_nonempty_expression_c_list():
    assert any(
        "expression_c" in e for e in check_derive_fc(_valid_derive(expression_c=[]))
    )
    assert any(
        "expression_c" in e for e in check_derive_fc(_valid_derive(expression_c="x"))
    )


def test_check_derive_fc_requires_four_domain_markers_in_expression_c():
    errs = check_derive_fc(
        _valid_derive(
            expression_c=[
                "domain.register: ok",
                "domain.carriers: ok",
                "domain.scannability: ok",
                # missing altitude
            ],
        ),
    )
    assert any("domain.altitude" in e for e in errs)


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
    assert any("expression_c" in e for e in errs)

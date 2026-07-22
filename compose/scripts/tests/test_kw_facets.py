#!/usr/bin/env python3
"""Tests for kw_facets parser and receipt helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from kw_facets import (  # noqa: E402
    find_active_open_collision,
    kw_criteria_path,
    materialize_kw_criteria,
    parse_kw_criteria_facets,
    silence_must_facets,
    validate_facet_id_for_lens,
)

_OPS_MD = """
## I

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW1 | Can state something |

## OPS

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW1 | Can state operability |

```json
{
  "facets": [
    {"id": "runtime_degradation", "kw": 1, "required": true},
    {"id": "steady_state_rollback", "kw": 1, "required": true},
    {"id": "cutover_migration_repair", "kw": 1, "required": true},
    {"id": "other", "kw": 1, "required": false}
  ]
}
```
"""


def test_parse_ops_facets_only():
    reg = parse_kw_criteria_facets(_OPS_MD)
    assert "I" not in reg
    assert "OPS" in reg
    ids = {f["id"] for f in reg["OPS"]}
    assert ids == {
        "runtime_degradation",
        "steady_state_rollback",
        "cutover_migration_repair",
        "other",
    }
    other = next(f for f in reg["OPS"] if f["id"] == "other")
    assert other["required"] is False


def test_other_must_be_optional():
    bad = """
## OPS
```json
{"facets": [{"id": "other", "kw": 1, "required": true}]}
```
"""
    with pytest.raises(ValueError, match="required=false"):
        parse_kw_criteria_facets(bad)


def test_validate_facet_rules():
    reg = parse_kw_criteria_facets(_OPS_MD)
    assert validate_facet_id_for_lens(None, lens="I", registry=reg) == []
    assert validate_facet_id_for_lens("x", lens="I", registry=reg)
    assert validate_facet_id_for_lens(None, lens="OPS", registry=reg)
    assert (
        validate_facet_id_for_lens(
            "runtime_degradation",
            lens="OPS",
            registry=reg,
        )
        == []
    )


def test_silence_and_receipts():
    reg = parse_kw_criteria_facets(_OPS_MD)
    facets = reg["OPS"]
    missing = silence_must_facets(
        lens="OPS",
        target_kw=1,
        facets=facets,
        opens=[],
        facts=[
            {
                "id": "F-1",
                "text": "migration only",
                "lens_tags": ["OPS"],
                "facet_id": "cutover_migration_repair",
            }
        ],
    )
    assert set(missing) == {"runtime_degradation", "steady_state_rollback"}

    missing2 = silence_must_facets(
        lens="OPS",
        target_kw=1,
        facets=facets,
        opens=[
            {
                "id": "O-1",
                "status": "open",
                "detected_under": "OPS",
                "facet_id": "runtime_degradation",
            }
        ],
        facts=[
            {
                "id": "F-1",
                "text": "migration",
                "lens_tags": ["OPS"],
                "facet_id": "cutover_migration_repair",
            },
            {
                "id": "F-2",
                "text": "no steady-state rollback protocol",
                "lens_tags": ["OPS"],
                "facet_id": "steady_state_rollback",
            },
        ],
    )
    assert missing2 == []


def test_materialize_kw_criteria(tmp_path):
    path = materialize_kw_criteria(tmp_path, _OPS_MD)
    assert path == kw_criteria_path(tmp_path)
    assert path.is_file()
    assert "OPS" in parse_kw_criteria_facets(path.read_text(encoding="utf-8"))


def test_active_open_collision():
    opens = [
        {
            "id": "O-1",
            "status": "open",
            "detected_under": "OPS",
            "kw": 1,
            "facet_id": "other",
        },
        {
            "id": "O-2",
            "status": "settled",
            "detected_under": "OPS",
            "kw": 1,
            "facet_id": "other",
            "resolved_by": ["F-1"],
        },
    ]
    hit = find_active_open_collision(
        opens,
        detected_under="OPS",
        kw=1,
        facet_id="other",
    )
    assert hit is not None and hit["id"] == "O-1"

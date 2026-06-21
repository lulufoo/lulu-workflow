#!/usr/bin/env python3
"""Tests for upstream_ssot supplementary path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

import bootstrap  # noqa: F401
from delivered_refs_schema import DeliveredRef  # noqa: E402
from upstream_ssot import resolve_supplementary_paths  # noqa: E402


def test_resolve_supplementary_from_scope_tail():
    scope = [
        DeliveredRef(type="tech-diagnostic", path="/abs/decision.md"),
        DeliveredRef(type="tech-design", path="/abs/design.md"),
    ]
    paths = resolve_supplementary_paths("tech-plan", scope, [])
    assert paths["design_doc_path"] == "/abs/design.md"


def test_resolve_supplementary_from_delivered_refs():
    delivered = [DeliveredRef(type="tech-design", path="/abs/design.md")]
    paths = resolve_supplementary_paths("tech-plan", [], delivered)
    assert paths["design_doc_path"] == "/abs/design.md"


def test_product_spec_has_no_supplementary():
    paths = resolve_supplementary_paths(
        "product-spec",
        [DeliveredRef(type="product-diagnostic", path="/abs/decision.md")],
        [],
    )
    assert paths == {}

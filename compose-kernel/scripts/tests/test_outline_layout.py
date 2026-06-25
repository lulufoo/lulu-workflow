#!/usr/bin/env python3
"""Tests for outline_layout.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from outline_layout import main, resolve_layout_for_section  # noqa: E402
from test_template_data import OUTLINE_REGISTRY_FEATURE  # noqa: E402


def test_resolve_layout_for_section_go_is_last_in_ov():
    payload = resolve_layout_for_section(OUTLINE_REGISTRY_FEATURE, "GO")
    assert payload["block_key"] == "OV"
    assert payload["last_in_block"] is True
    assert payload["first_in_block"] is False
    assert payload["block_intents"] == ["CTX", "GO"]
    assert payload["block_heading"] == "Overview"


def test_resolve_layout_for_section_ctx_is_first_in_ov():
    payload = resolve_layout_for_section(OUTLINE_REGISTRY_FEATURE, "CTX")
    assert payload["first_in_block"] is True
    assert payload["last_in_block"] is False


def test_resolve_cli(tmp_path: Path):
    outline_path = tmp_path / "outline-registry.json"
    outline_path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    rc = main(
        [
            "resolve",
            "--section",
            "GO",
            "--outline-path",
            str(outline_path),
        ]
    )
    assert rc == 0

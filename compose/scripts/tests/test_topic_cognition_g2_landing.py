#!/usr/bin/env python3
"""Static landing checks for G2 topic cognition (archive-19.0)."""

from __future__ import annotations

from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_GATE = _COMPOSE / "inductive-runner" / "gates" / "g2-topic-loop.md"
_REF = _COMPOSE / "inductive-runner" / "references" / "topic-cognition-model.md"
_SPINE = _COMPOSE / "inductive-runner" / "SKILL.md"


def test_topic_cognition_reference_exists_and_names_tools():
    text = _REF.read_text(encoding="utf-8")
    assert "gap-landscape" in text
    assert "topic-portrait" in text
    assert "Grain" in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_g2_gate_declares_tools_and_points_at_reference():
    text = _GATE.read_text(encoding="utf-8")
    assert "`gap-landscape`" in text
    assert "`topic-portrait`" in text
    assert "topic-cognition-model.md" in text
    assert "future compose/references" not in text
    assert "docs/" not in text
    assert "archive-" not in text
    assert "portrait口径" not in text


def test_inductive_spine_mentions_topic_cognition_tools():
    text = _SPINE.read_text(encoding="utf-8")
    assert "gap-landscape" in text
    assert "topic-portrait" in text
    assert "topic-cognition-model.md" in text

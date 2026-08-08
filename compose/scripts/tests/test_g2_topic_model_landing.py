#!/usr/bin/env python3
"""Static landing checks for G2 topic model (archive-20.0)."""

from __future__ import annotations

from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_GATE = _COMPOSE / "inductive-runner" / "gates" / "g2-topic-loop.md"
_REF = _COMPOSE / "inductive-runner" / "references" / "g2-topic-model.md"
_SPINE = _COMPOSE / "inductive-runner" / "SKILL.md"
_OLD_REF = _COMPOSE / "inductive-runner" / "references" / "topic-cognition-model.md"


def test_g2_topic_model_reference_exists_and_names_tools():
    assert _REF.is_file()
    assert not _OLD_REF.exists()
    text = _REF.read_text(encoding="utf-8")
    assert "topic-landscape" in text
    assert "topic-portrait" in text
    assert "## Topic" in text
    assert "`gap`" in text
    assert "adopted" in text
    assert "concluded" in text
    assert "### Adopt" in text
    assert "three inseparable facets" in text
    assert "pre-adopt clarify" not in text
    assert "Human confirms once" not in text
    assert "Grain" in text
    assert "gap-landscape" not in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_g2_gate_declares_tools_and_points_at_reference():
    text = _GATE.read_text(encoding="utf-8")
    assert "`topic-landscape`" in text
    assert "`topic-portrait`" in text
    assert "g2-topic-model.md" in text
    assert "topic_exit" in text
    assert "record-topic-landscape" in text
    assert "record-g2-topic-exit" in text
    assert "## Tool boundaries" in text
    assert "## Declared tools" not in text
    assert "## Workflow" in text
    assert "### Seeking" in text
    assert "### Work a topic" in text
    assert "### Exit" in text
    assert "### Display refresh (optional)" in text
    assert "## Session boundaries" in text
    assert "## Session notions" not in text
    assert "sole authority" in text
    assert "adopt a candidate from dialogue or `topic-landscape`" in text
    assert "Exit receipts are the pre-close landscape and exit receipt" in text
    assert "owning contracts" in text
    assert "Direct dialogue may propose and adopt a topic without a landscape." in text
    assert "guide from the most-upstream `gap`" in text
    assert "Presentation is required; confirmation is not." in text
    assert "Gate-close requires the D1+D2 design goal" in text
    assert "matching pre-close landscape, exit receipt, and `payload.topic_exit`" in text
    assert "pre_close` and require confirmation" in text
    assert "After `fact-runner` completes successfully, return to Seeking." in text
    assert "Only after `fact-runner` consume emits `stale_signal`" in text
    assert "### Main flow" not in text
    assert "### Branches" not in text
    assert "### Close" not in text
    assert "## Phase map" not in text
    assert "## Phase → bind" not in text
    assert "pre-adopt clarify" not in text
    assert "clarify (pre-adopt)" not in text
    assert "human confirm before deep work" not in text
    assert "gap-landscape" not in text
    assert "topic-cognition-model.md" not in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_inductive_spine_mentions_g2_topic_model_tools():
    text = _SPINE.read_text(encoding="utf-8")
    assert "topic-landscape" in text
    assert "topic-portrait" in text
    assert "g2-topic-model.md" in text
    assert "topic_exit" in text
    assert "record-topic-landscape" in text
    assert "record-g2-topic-exit" in text
    assert "gap-landscape" not in text
    assert "topic-cognition-model.md" not in text

def test_g2_topic_model_mentions_receipt_persist():
    text = _REF.read_text(encoding="utf-8")
    assert "record-topic-landscape" in text
    assert "record-g2-topic-exit" in text
    assert "Honest boundary" in text

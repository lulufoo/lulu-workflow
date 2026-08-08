#!/usr/bin/env python3
"""Static checks for the inductive topic model's G2 integration."""

from __future__ import annotations

from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_GATE = _COMPOSE / "inductive-runner" / "gates" / "g2-topic-loop.md"
_REF = _COMPOSE / "inductive-runner" / "references" / "inductive-topic-model.md"
_SPINE = _COMPOSE / "inductive-runner" / "SKILL.md"
_G2_REF = _COMPOSE / "inductive-runner" / "references" / "g2-topic-model.md"
_OLD_REF = _COMPOSE / "inductive-runner" / "references" / "topic-cognition-model.md"


def test_inductive_topic_model_is_generic_and_names_tools():
    assert _REF.is_file()
    assert not _G2_REF.exists()
    assert not _OLD_REF.exists()
    text = _REF.read_text(encoding="utf-8")
    assert "topic-landscape" in text
    assert "topic-portrait" in text
    assert "## Inputs" in text
    assert "## Domain model" in text
    assert "#### Framing" in text
    assert "### Topic" in text
    assert "#### Grain" in text
    assert "### Topic DAG" in text
    assert "## Topic discovery" in text
    assert "parallel candidate sources" in text
    assert "## Induction portrait" in text
    assert "## Tool contracts" in text
    assert "### `topic-landscape`" in text
    assert "### `topic-portrait`" in text
    assert "`gap`" in text
    assert "adopted" in text
    assert "concluded" in text
    assert "### Adopt" not in text
    assert "three inseparable facets" not in text
    assert "pre-adopt clarify" not in text
    assert "Human confirms once" not in text
    assert "Grain" in text
    assert "## Grain (definition)" not in text
    assert "## Portrait — shared pool, two lenses" not in text
    assert "### Topic model" not in text
    assert "### Topic DAG model" not in text
    assert "### Portrait model" not in text
    assert "## Cognitive model" not in text
    assert "G2" not in text
    assert "Gate" not in text
    assert "D1" not in text
    assert "D2" not in text
    assert "Positioning triple" not in text
    assert "## Seeking DAG" not in text
    assert "## Tool protocol" not in text
    assert "**Trigger (gate):**" not in text
    assert "**Steps:**" not in text
    assert "current-topic relation" in text
    assert "without a\ncurrent-topic relation" in text
    assert "then the Topic DAG" in text
    assert "with\nits current-topic relation" in text
    assert "then the topic's framing" in text
    assert "Convergence portrait" not in text
    assert "Shared capability pool" not in text
    assert "lens 1" not in text
    assert "lens 2" not in text
    assert "default guidance comes from" not in text
    assert "gap-landscape" not in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_g2_gate_declares_tools_and_points_at_reference():
    text = _GATE.read_text(encoding="utf-8")
    assert "`topic-landscape`" in text
    assert "`topic-portrait`" in text
    assert "inductive-topic-model.md" in text
    assert "g2-topic-model.md" not in text
    assert "Topic discovery" in text
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
    assert "## Topic operation" in text
    assert "### Adopt" in text
    assert "Human confirmation is" in text
    assert "the sole authority to adopt it." in text
    assert "sole authority" in text
    assert "adopt a candidate from dialogue or `topic-landscape`" in text
    assert "Exit receipts are the pre-close landscape and exit receipt" in text
    assert "owning contracts" in text
    assert "Direct dialogue may propose and adopt a topic without a landscape." in text
    assert "guide from the most-upstream `gap`" in text
    assert "Presentation is required; confirmation is not." in text
    assert "Gate-close requires the D1+D2 design goal" in text
    assert "matching pre-close landscape, exit receipt, and `payload.topic_exit`" in text
    assert "purpose=pre_close" in text
    assert "perform `Adopt`." in text
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


def test_inductive_spine_mentions_inductive_topic_model_tools():
    text = _SPINE.read_text(encoding="utf-8")
    assert "topic-landscape" in text
    assert "topic-portrait" in text
    assert "inductive-topic-model.md" in text
    assert "g2-topic-model.md" not in text
    assert "topic_exit" in text
    assert "record-topic-landscape" in text
    assert "record-g2-topic-exit" in text
    assert "gap-landscape" not in text
    assert "topic-cognition-model.md" not in text

def test_g2_gate_owns_landscape_receipt_persist():
    model = _REF.read_text(encoding="utf-8")
    gate = _GATE.read_text(encoding="utf-8")
    assert "record-topic-landscape" not in model
    assert "record-g2-topic-exit" not in model
    assert "record-topic-landscape" in gate
    assert "caller-reported `gap_remaining`" in gate

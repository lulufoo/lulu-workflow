#!/usr/bin/env python3
"""Static checks for Topic modeling + tool split and G2 integration."""

from __future__ import annotations

from pathlib import Path


_COMPOSE = Path(__file__).resolve().parents[2]
_GATE = _COMPOSE / "inductive-runner" / "gates" / "g2-topic-loop.md"
_TOPIC_REF = _COMPOSE / "inductive-runner" / "references" / "topic-model.md"
_LANDSCAPE_REF = (
    _COMPOSE / "inductive-runner" / "references" / "topic-landscape.md"
)
_PORTRAIT_REF = (
    _COMPOSE / "inductive-runner" / "references" / "topic-portrait.md"
)
_DAG_REF = _COMPOSE / "inductive-runner" / "references" / "topic-dag-model.md"
_OLD_REF = (
    _COMPOSE / "inductive-runner" / "references" / "inductive-topic-model.md"
)
_SPINE = _COMPOSE / "inductive-runner" / "SKILL.md"
_ARC_RUNNER = _COMPOSE / "narrative-arc-runner" / "SKILL.md"
_G2_REF = _COMPOSE / "inductive-runner" / "references" / "g2-topic-model.md"
_COGNITION_REF = (
    _COMPOSE / "inductive-runner" / "references" / "topic-cognition-model.md"
)


def test_topic_model_is_modeling_layer_only():
    assert _TOPIC_REF.is_file()
    assert _LANDSCAPE_REF.is_file()
    assert _PORTRAIT_REF.is_file()
    assert not _DAG_REF.exists()
    assert not _OLD_REF.exists()
    assert not _G2_REF.exists()
    assert not _COGNITION_REF.exists()

    topic = _TOPIC_REF.read_text(encoding="utf-8")

    assert "## Inputs" in topic
    assert "## Topic" in topic
    assert "### States" in topic
    assert "`gap`" in topic
    assert "adopted" in topic
    assert "concluded" in topic
    assert "## Grain" in topic
    assert "Grain is independent of Topic state." in topic
    assert "neither seeking priority nor DAG\n" in topic
    assert "owns no grain persistence" in topic
    assert "## Topic DAG" in topic
    assert "**upstream frontier**" in topic
    assert "The DAG excludes adopted Topics." in topic
    assert "presentation concern, not part of the\nTopic DAG itself" in topic
    assert "Topic DAG topology" in topic
    assert "seeking-DAG" not in topic
    assert "Current Topic" not in topic
    assert "## Discovery" not in topic
    assert "## `topic-portrait`" not in topic
    assert "## `topic-landscape`" not in topic
    assert "## Presentation" not in topic
    assert "**Select:**" not in topic
    assert "**Grounding**" not in topic
    assert "Induction portrait" not in topic
    assert "## Topic discovery" not in topic
    assert "Human candidate signals" not in topic
    assert "Human discovery" not in topic
    assert "source anchor" not in topic.lower()
    assert "[`topic-landscape.md`]" not in topic
    assert "[`topic-portrait.md`]" not in topic

    assert "G2" not in topic
    assert "Gate" not in topic
    assert "D1" not in topic
    assert "D2" not in topic
    assert "docs/" not in topic
    assert "archive-" not in topic
    assert "gap-landscape" not in topic


def test_topic_landscape_tool_contract():
    text = _LANDSCAPE_REF.read_text(encoding="utf-8")

    assert "[`topic-model.md`](topic-model.md)" in text
    assert "## Purpose" in text
    assert "## Inputs" in text
    assert "**Human corrections**" in text
    assert "## Delivers" in text
    assert "**Seeking context**" in text
    assert "**Direction**" in text
    assert "**Settled coverage**" in text
    assert "**Overall unresolved areas**" in text
    assert "## Discovery" in text
    assert "Applies when deriving the initial temporary `gap` Topic set." in text
    assert "**Source**" in text
    assert "**Recompute**" in text
    assert "**Authority**" in text
    assert "**Human role**" not in text
    assert "## Presentation" in text
    assert "**Landscape graph**" in text
    assert "full landscape" in text
    assert "Topic DAG plus settled context" in text
    assert "color =" in text
    assert "settled /" in text
    assert "frontier / un-frontier" in text
    assert "## Build" in text
    assert "Discover per Discovery" in text
    assert "assemble the Topic DAG" in text
    assert "## Review" in text
    assert "The human may add, correct, or remove Topics." in text
    assert "## Select" in text
    assert "selection of a `gap` node only" in text
    assert "settled context\nnodes are not selectable" in text
    assert "source anchor" in text.lower()
    assert "landscape-receipt" in text
    assert "summary" in text
    assert "## Invalidate" in text
    assert "Rebuild, re-present, and reconfirm before selection." in text
    assert "## Constraints" in text
    assert "display-only" in text
    assert "## `topic-portrait`" not in text
    assert "### `topic-question-driver`" not in text
    assert "## Grain" not in text
    assert "## Topic DAG" not in text

    assert "G2" not in text
    assert "Gate" not in text
    assert "docs/" not in text
    assert "archive-" not in text
    assert "gap-landscape" not in text


def test_topic_portrait_tool_contract():
    text = _PORTRAIT_REF.read_text(encoding="utf-8")

    assert "[`topic-model.md`](topic-model.md)" in text
    assert "## Purpose" in text
    assert "## Prerequisite" in text
    assert "## Delivers" in text
    assert "**Grounding**" in text
    assert "**Closure target**" in text
    assert "**Boundary**" in text
    assert "## Facts-first grounding" in text
    assert "return `Blocked`" in text
    assert "## Constraints" in text
    assert "## Topic DAG" not in text
    assert "## Discovery" not in text
    assert "## Presentation" not in text
    assert "`topic-landscape`" not in text
    assert "seeking map" not in text
    assert "seeking landscape" in text

    assert "G2" not in text
    assert "Gate" not in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_g2_gate_declares_tools_and_points_at_split_references():
    text = _GATE.read_text(encoding="utf-8")
    assert "`topic-landscape`" in text
    assert "`topic-portrait`" in text
    assert "topic-model.md" in text
    assert "topic-landscape.md" in text
    assert "topic-portrait.md" in text
    assert "topic-dag-model.md" not in text
    assert "inductive-topic-model.md" not in text
    assert "Topic discovery" not in text
    assert "topic_exit" in text
    assert "record-topic-landscape" in text
    assert "record-g2-topic-exit" in text
    assert "## Tool boundaries" in text
    assert "## Declared tools" not in text
    assert "## Workflow" not in text
    assert "### Seeking" not in text
    assert "### Work a topic" not in text
    assert "### Exit" not in text
    assert "### Display refresh (optional)" not in text
    assert "## Routing" in text
    assert "## Close" in text
    assert "## Session boundaries" in text
    assert "## Topic operation" not in text
    assert "### Adopt" not in text
    assert "Autonomously build the initial `topic-landscape`" in text
    assert "reconcile human corrections and re-present" in text
    assert "Treat human correction as a parallel discovery source" in text
    assert "select a `gap` node (caller then adopts)" in text
    assert "select its node for adoption" not in text
    assert "seeking landscape or close proof" in text
    assert "seeking map" not in text
    assert "G2 Topic contracts:" not in text
    assert "`topic-model`: generic contract in `../references/topic-model.md`" in text
    assert "`topic-landscape`: generic contract in `../references/topic-landscape.md`" in text
    assert "`topic-portrait`: generic contract in `../references/topic-portrait.md`" in text
    assert "Exit receipts are the pre-close landscape and exit receipt" in text
    assert "owning contracts" in text
    assert "Human request" in text
    assert "Any time while G2 is active." in text
    assert "$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_ASYNC" in text
    assert "$SUBAGENT_AWAIT_SYNC" not in text
    assert "Heading = phase; first line = after which action" in text
    assert "### Topic landscape" in text
    assert "### Topic portrait" in text
    assert "### Topic question drive" in text
    assert "### Topic conclusion" in text
    assert "### Close" not in text
    assert "Invoke on seeking entry, refresh, Topic proposal, or invalid landscape." in text
    assert "After\n`topic-landscape` runs: behavior map" in text
    assert "After `topic-portrait` runs: behavior map" in text
    assert "After `topic-question-driver` runs: behavior map" in text
    assert "After a Conclusion Candidate or free-dialogue conclusion: behavior map" in text
    assert "purpose=seek|refresh" in text
    assert "caller-reported `gap_remaining`" in text
    assert "prefer `topic-question-driver`" in text
    assert "After every `topic-landscape` result" not in text
    assert "Signal / condition" not in text
    assert "### `topic-landscape`" not in text
    assert "### `topic-portrait`" not in text
    assert "--scope <selected-scope> --human-adopted" in text
    assert "--scope <corrected-scope> --human-adopted" in text
    assert "State which path is active" in text
    assert "`Next Question` → dialogue" in text
    assert "`Conclusion Candidate`" in text
    assert "set-conclusion" in text
    assert "confirm-conclusion" in text
    assert "stale_signal" in text
    assert "purpose=pre_close" in text
    assert "human candidate signals" not in text
    assert "Direct dialogue may propose and adopt" not in text
    assert "most-upstream `gap`" not in text
    assert "`topic_loop_done=true`" in text
    assert "`design_goal_met=true`" in text
    assert "`human_exit_confirmed=true`" in text
    assert "`topic_exit` matching the recorded" in text
    assert "landscape must be `pre_close`" in text
    assert "run and `gap_remaining` must\n  match" in text
    assert "**cleared** requires zero remaining" in text
    assert "no Topic conclusion may remain unconfirmed" in text
    assert "gap-landscape" not in text
    assert "topic-cognition-model.md" not in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_inductive_spine_points_at_split_g2_contracts():
    text = _SPINE.read_text(encoding="utf-8")
    assert "G2 Topic Loop" in text
    assert "gates/g2-topic-loop.md" in text
    assert "references/topic-model.md" in text
    assert "references/topic-landscape.md" in text
    assert "references/topic-portrait.md" in text
    assert "references/topic-dag-model.md" not in text
    assert "references/inductive-topic-model.md" not in text


def test_g2_gate_owns_landscape_receipt_persist():
    topic = _TOPIC_REF.read_text(encoding="utf-8")
    landscape = _LANDSCAPE_REF.read_text(encoding="utf-8")
    portrait = _PORTRAIT_REF.read_text(encoding="utf-8")
    gate = _GATE.read_text(encoding="utf-8")
    assert "record-topic-landscape" not in topic
    assert "record-topic-landscape" not in landscape
    assert "record-topic-landscape" not in portrait
    assert "record-g2-topic-exit" not in topic
    assert "record-g2-topic-exit" not in landscape
    assert "record-g2-topic-exit" not in portrait
    assert "record-topic-landscape" in gate
    assert "caller-reported `gap_remaining`" in gate


def test_collab_arc_rebuild_is_g2_owned():
    spine = _SPINE.read_text(encoding="utf-8")
    gate = _GATE.read_text(encoding="utf-8")
    runner = _ARC_RUNNER.read_text(encoding="utf-8")

    assert "converge design through human-adopted topics" in spine
    assert "human-confirmed topic exit" in spine
    assert "optional collab rebuild via" not in spine
    assert "$SUBAGENT_AWAIT_SYNC" not in runner
    assert "$SUBAGENT_AWAIT_ASYNC" not in runner
    assert "## Input" in runner
    assert "OUTPUT_PATH:" in runner
    assert "MOUNT:" in runner
    assert "contracts/delivery.md" in runner
    assert "target=collab" not in runner
    assert "$SUBAGENT_AWAIT_SYNC" not in gate
    assert "$SUBAGENT_AWAIT_ASYNC" in gate
    assert "narrative-arc-runner" in gate
    assert "$NARRATIVE_ARC_COLLAB_CTL" not in gate

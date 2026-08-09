#!/usr/bin/env python3
"""Static checks for the split Topic models and their G2 integration."""

from __future__ import annotations

from pathlib import Path


_COMPOSE = Path(__file__).resolve().parents[2]
_GATE = _COMPOSE / "inductive-runner" / "gates" / "g2-topic-loop.md"
_TOPIC_REF = _COMPOSE / "inductive-runner" / "references" / "topic-model.md"
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


def test_topic_and_dag_models_have_one_way_ownership():
    assert _TOPIC_REF.is_file()
    assert _DAG_REF.is_file()
    assert not _OLD_REF.exists()
    assert not _G2_REF.exists()
    assert not _COGNITION_REF.exists()

    topic = _TOPIC_REF.read_text(encoding="utf-8")
    dag = _DAG_REF.read_text(encoding="utf-8")

    assert "## Inputs" in topic
    assert "## Topic" in topic
    assert "### States" in topic
    assert "## `topic-portrait`" in topic
    assert "**Grounding**" in topic
    assert "**Closure target**" in topic
    assert "**Boundary**" in topic
    assert "**Facts-first grounding:**" in topic
    assert "return `Blocked`" in topic
    assert "`gap`" in topic
    assert "adopted" in topic
    assert "concluded" in topic
    assert "Induction portrait" not in topic
    assert "## Topic discovery" not in topic
    assert "Human candidate signals" not in topic
    assert "## Grain" in topic
    assert "Grain is independent of Topic state." in topic
    assert "neither seeking priority nor DAG\n" in topic
    assert "owns no grain persistence" in topic
    assert "## Topic DAG" not in topic
    assert "### `topic-landscape`" not in topic
    assert "Framing" not in topic
    assert "source anchor" not in topic.lower()

    assert "[`topic-model.md`](topic-model.md)" in dag
    assert "## Discovery" in dag
    assert "AI autonomously derives the initial working set" in dag
    assert "main discovery path" in dag
    assert "keeps no hidden\nTopic registry" in dag
    assert "Human changes are corrections" in dag
    assert "not a parallel\ndiscovery source" in dag
    assert "Human discovery" not in dag
    assert "Human candidate signals" not in dag
    assert "## Grain" not in dag
    assert "## Topic DAG" in dag
    assert "grain assigned under `topic-model.md`" in dag
    assert "**upstream frontier**" in dag
    assert "### Source anchor" not in dag
    assert "anchor is absent before selection, required for\nadoption" in dag
    assert "landscape-receipt summary" in dag
    assert "## `topic-landscape`" in dag
    assert "**Human corrections**" in dag
    assert "**Seeking context**" in dag
    assert "**Direction**" in dag
    assert "**Settled coverage**" in dag
    assert "**Overall unresolved areas**" in dag
    assert "then the Topic DAG" in dag
    assert "grain labels" in dag
    assert "**Build:** AI discovers" in dag
    assert "**Review:** The human may add, correct, or remove Topics." in dag
    assert "re-presents the complete view" in dag
    assert "**Select:** Human confirmation authorizes node selection" in dag
    assert "**Invalidate:**" in dag
    assert "Rebuild, re-present, and reconfirm before selection." in dag
    assert "## `topic-portrait`" not in dag
    assert "### `topic-portrait`" not in dag
    assert "### `topic-question-driver`" not in dag
    assert "## Induction portrait" not in dag

    for text in (topic, dag):
        assert "G2" not in text
        assert "Gate" not in text
        assert "D1" not in text
        assert "D2" not in text
        assert "docs/" not in text
        assert "archive-" not in text
        assert "gap-landscape" not in text


def test_g2_gate_declares_tools_and_points_at_split_references():
    text = _GATE.read_text(encoding="utf-8")
    assert "`topic-landscape`" in text
    assert "`topic-portrait`" in text
    assert "topic-model.md" in text
    assert "topic-dag-model.md" in text
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
    assert "Exit receipts are the pre-close landscape and exit receipt" in text
    assert "owning contracts" in text
    assert "Human request" in text
    assert "Any time while G2 is active." in text
    assert "$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_ASYNC" in text
    assert "$SUBAGENT_AWAIT_SYNC" not in text
    assert "do not treat these entries as a scripted event chain" in text
    assert "Seeking entry, refresh, Topic proposal, or invalid landscape" in text
    assert "A proposal enters its Review loop" in text
    assert "require confirmation and node selection before binding" in text
    assert "Human selects a node from the current confirmed landscape" in text
    assert "--scope <selected-scope> --human-adopted" in text
    assert "then rerun the portrait" in text
    assert "Do not enter deep work before a non-`Blocked` portrait" in text
    assert "Human materially corrects `Closure target`" in text
    assert "--scope <corrected-scope> --human-adopted" in text
    assert "Non-`Blocked` portrait presented" in text
    assert "Driver returns `Next Question` / `Blocked`" in text
    assert "`Topic Closure Candidate` or free-dialogue conclusion" in text
    assert "set-conclusion` → human confirmation → `$TOPIC_CURRENT_CTL confirm-conclusion`" in text
    assert "on success, return to Seeking" in text
    assert "`fact-runner` consume emits `stale_signal`" in text
    assert "human candidate signals" not in text
    assert "Direct dialogue may propose and adopt" not in text
    assert "most-upstream `gap`" not in text
    assert "purpose=pre_close" in text
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
    assert "references/topic-dag-model.md" in text
    assert "references/inductive-topic-model.md" not in text


def test_g2_gate_owns_landscape_receipt_persist():
    topic = _TOPIC_REF.read_text(encoding="utf-8")
    dag = _DAG_REF.read_text(encoding="utf-8")
    gate = _GATE.read_text(encoding="utf-8")
    assert "record-topic-landscape" not in topic
    assert "record-topic-landscape" not in dag
    assert "record-g2-topic-exit" not in topic
    assert "record-g2-topic-exit" not in dag
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
    assert "| Entry | Caller | Input | Done when |" in runner
    assert (
        "| `target=collab` | G2 Topic Loop | Collab Input below | "
        "Summary; Viewer mount on success |"
    ) in runner
    assert "$SUBAGENT_AWAIT_SYNC" not in gate
    assert "$SUBAGENT_AWAIT_ASYNC" in gate

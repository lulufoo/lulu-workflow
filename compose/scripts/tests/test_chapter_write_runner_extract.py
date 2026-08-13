#!/usr/bin/env python3
"""SKILL wiring checks for chapter-write-runner extract + Writing orchestrator."""

from __future__ import annotations

from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_WRITING = (_COMPOSE / "writing-runner" / "SKILL.md").read_text(encoding="utf-8")
_WRITE = (_COMPOSE / "chapter-write-runner" / "SKILL.md").read_text(encoding="utf-8")
_PROTOCOL = (
    _COMPOSE / "chapter-write-runner" / "references" / "write-protocol.md"
).read_text(encoding="utf-8")
_DELIVERY = (
    _COMPOSE / "chapter-write-runner" / "contracts" / "delivery.md"
).read_text(encoding="utf-8")


def test_writing_step1_no_longer_preloads_write_frameworks():
    step1 = _WRITING.split("### Step 2")[0]
    assert "$RESOLVE_ROLE" not in step1
    assert "$RESOLVE_DOMAIN" not in step1
    assert "section-form-registry" not in step1
    assert "section-kw-criteria" not in step1
    assert "init-doc`" not in step1.split("**Done:**")[0]
    assert "$CODE_GROUNDING" in step1
    assert "Proceed to Step 2" in step1


def test_writing_step5_dispatches_chapter_write_runner():
    assert "chapter-write-runner/SKILL.md" in _WRITING
    assert "ARC_PATH: _narrative-arc.json" in _WRITING
    assert "OUTPUT_DOC_PATH: <$OUTPUT_DOC_PATH>" in _WRITING
    assert "$SUBAGENT_TOOL" in _WRITING
    assert "### Step 5 — Chapter write + assemble" in _WRITING
    # Writing orchestrator must not keep the old inline write wall
    assert "#### 4.W — Write-by-sub-topic-chapter" not in _WRITING
    step5 = _WRITING.split("### Step 5")[1].split("### Step 6")[0]
    assert "section-form-registry" not in step5


def test_write_runner_input_five_fields():
    for field in (
        "REVISION_DIR:",
        "PROJECT_ROOT:",
        "CYCLE_ID:",
        "OUTPUT_DOC_PATH:",
        "ARC_PATH:",
    ):
        assert field in _WRITE
    assert "COMPOSE_PROFILE:" not in _WRITE
    assert "ARC_PATH: _narrative-arc.json" in _WRITE
    assert "$CODE_GROUNDING" in _DELIVERY
    assert "--profile" not in _DELIVERY


def test_step4_write_semantics_preserved_in_protocol():
    required = [
        "claim-current",
        "待决",
        "writing_cognition",
        "lens_intent",
        "assemble-arc",
        "no `--chapter`",
    ]
    for phrase in required:
        assert phrase in _PROTOCOL, phrase
    assert "COMPOSE_PROFILE" not in _PROTOCOL
    assert "--profile" not in _PROTOCOL
    assert "writing_cognition" in _PROTOCOL
    assert "context.role" in _PROTOCOL or "context.domain" in _PROTOCOL
    assert "Phase 0" in _DELIVERY
    assert "init-doc" in _DELIVERY

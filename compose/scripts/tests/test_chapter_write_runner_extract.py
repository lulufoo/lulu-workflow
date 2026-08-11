#!/usr/bin/env python3
"""SKILL wiring checks for chapter-write-runner extract (archive-26.0 T4/T5/T8)."""

from __future__ import annotations

from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_INIT = (_COMPOSE / "initializing-runner" / "SKILL.md").read_text(encoding="utf-8")
_WRITE = (_COMPOSE / "chapter-write-runner" / "SKILL.md").read_text(encoding="utf-8")
_PROTOCOL = (
    _COMPOSE / "chapter-write-runner" / "references" / "write-protocol.md"
).read_text(encoding="utf-8")
_DELIVERY = (
    _COMPOSE / "chapter-write-runner" / "contracts" / "delivery.md"
).read_text(encoding="utf-8")


def test_init_step1_no_longer_preloads_write_frameworks():
    step1 = _INIT.split("### Step 2")[0]
    assert "$RESOLVE_ROLE" not in step1
    assert "$RESOLVE_DOMAIN" not in step1
    assert "section-form-registry" not in step1
    assert "section-kw-criteria" not in step1
    assert "init-doc`" not in step1.split("**Done:**")[0]
    assert "$CODE_GROUNDING" in step1
    assert "Do **not** require Role/Domain resolve" in step1


def test_init_step4_inline_loads_chapter_write_runner():
    assert "chapter-write-runner/SKILL.md" in _INIT
    assert "ARC_PATH: _narrative-arc.json" in _INIT
    assert "OUTPUT_DOC_PATH: <$OUTPUT_DOC_PATH>" in _INIT
    assert "wrote_bodies=true" in _INIT
    # Init must not keep the old Step 4 write wall
    assert "#### 4.W — Write-by-sub-topic-chapter" not in _INIT
    assert "section-form-registry" not in _INIT.split("### Step 4")[1].split("### Step 5")[0]


def test_write_runner_input_six_fields():
    for field in (
        "REVISION_DIR:",
        "PROJECT_ROOT:",
        "COMPOSE_PROFILE:",
        "CYCLE_ID:",
        "OUTPUT_DOC_PATH:",
        "ARC_PATH:",
    ):
        assert field in _WRITE
    assert "$CODE_GROUNDING" in _WRITE  # named as Must not
    assert "Must not (Input)" in _WRITE
    assert "ARC_PATH: _narrative-arc.json" in _WRITE
    assert "This wave" in _WRITE and "_narrative-arc.json" in _WRITE
    assert "This wave" in _DELIVERY
    assert "default basename only" in _DELIVERY


def test_step4_write_semantics_preserved_in_protocol():
    required = [
        "claim-current",
        "begin.facts",
        "待决",
        "already_running",
        "missing_fact_ids",
        "writing_cognition",
        "lens_intent",
        "assemble-arc",
        "Must not (Write substance source)",
        "Read `_facts.json`",
        "begin --chapter",
        "<!-- chapter:{cid} -->",
    ]
    for phrase in required:
        assert phrase in _PROTOCOL, phrase
    assert "writing_cognition" in _PROTOCOL
    assert "context.role" in _PROTOCOL or "context.domain" in _PROTOCOL
    assert "session context" in _DELIVERY or "Session context" in _DELIVERY
    assert "Phase 0" in _PROTOCOL
    assert "init-doc" in _PROTOCOL.split("## Artifacts")[0]

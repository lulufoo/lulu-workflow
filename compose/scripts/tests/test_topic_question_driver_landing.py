#!/usr/bin/env python3
"""Static and install checks for the topic question driver landing."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_COMPOSE = Path(__file__).resolve().parents[2]
_WORKFLOW = _COMPOSE.parent
_REPO = _WORKFLOW.parent
_MODEL = _COMPOSE / "inductive-runner" / "references" / "topic-model.md"
_DRIVER = _COMPOSE / "inductive-runner" / "references" / "topic-question-driver.md"
_GATE = _COMPOSE / "inductive-runner" / "gates" / "g2-topic-loop.md"
_SHARED_ASK = _WORKFLOW / "shared" / "references" / "ask-protocol.md"
_OLD_ASK = _WORKFLOW / "decision" / "references" / "ask-protocol.md"
_ARCH = _REPO / "docs" / "skill" / "skill-architecture-constraints.md"
_INSTALLER = _REPO / "lulu-meta-skill" / "scripts" / "install.py"

_Q = _WORKFLOW / "decision" / "runners" / "q-problem-runner" / "SKILL.md"
_GL = _WORKFLOW / "decision" / "runners" / "gl-grill-runner" / "SKILL.md"
_E = _WORKFLOW / "decision" / "runners" / "e-direction-runner" / "SKILL.md"


def test_driver_contract_and_optional_g2_routing():
    assert _DRIVER.is_file()
    driver = _DRIVER.read_text(encoding="utf-8")
    model = _MODEL.read_text(encoding="utf-8")
    gate = _GATE.read_text(encoding="utf-8")

    assert "## Goal" in driver
    assert "minimum-judgment / closure-review loop" in driver
    assert "### `Next Question`" in driver
    assert "### `Topic Closure Candidate`" in driver
    assert "### `Blocked`" not in driver
    assert "ordinary dialogue" in driver
    assert "$SKILL_ROOT/shared/references/ask-protocol.md" in driver
    assert "does not persist intermediate decisions" in driver
    assert "`/converge` is neither required nor invoked" in driver
    assert "presented portrait's `Grounding`, `Closure target`, and `Boundary`" in driver
    assert "settled target facts outrank project" in driver

    assert "caller workflow" in model

    assert "may optionally invoke `topic-question-driver` after the portrait" in gate
    assert "### Topic question drive" in gate
    assert "After `topic-question-driver` runs: behavior map" in gate
    assert "prefer `topic-question-driver`" in gate
    assert "`Next Question` → dialogue" in gate
    assert "`Topic Closure Candidate`" in gate


def test_shared_ask_protocol_is_single_runtime_ssot():
    assert _SHARED_ASK.is_file()
    assert not _OLD_ASK.exists()
    ask = _SHARED_ASK.read_text(encoding="utf-8")

    assert "Bound the candidate first" in ask
    assert "Collect-or-Ask first" in ask
    assert "Explore to sufficiency" in ask
    assert "Ground the candidate" in ask
    assert "Recommend" in ask
    assert "Ask Protocol G2" in ask
    assert "preserve the uncertainty" in ask
    assert "Minimal Explore" not in ask
    assert "Project-ground" not in ask
    assert "Ask Protocol G7" not in ask

    shared_ref = "$SKILL_ROOT/shared/references/ask-protocol.md"
    q = _Q.read_text(encoding="utf-8")
    gl = _GL.read_text(encoding="utf-8")
    e = _E.read_text(encoding="utf-8")
    assert shared_ref in q
    assert shared_ref in gl
    assert shared_ref in e
    assert "| `probe` | Any goal has a gap | Apply ask-protocol" in q
    assert "before the first probe in each GL entry, read" in gl
    assert "| `probe` | Either goal not met | Apply ask-protocol" in gl
    assert "| `align` | Closable candidate set ready;" in e
    assert "Do **not** apply ask-protocol." in e

    for runtime_md in _WORKFLOW.rglob("*.md"):
        assert "$SKILL_DIR/references/ask-protocol.md" not in runtime_md.read_text(
            encoding="utf-8",
        )


def test_shared_is_an_allowlisted_leaf():
    arch = _ARCH.read_text(encoding="utf-8")
    assert "`shared` is a references-only leaf library" in arch
    assert "compose | decision" in arch
    assert "→  shared" in arch
    assert "shared           ↛  *" in arch


def test_fresh_install_carries_shared_protocol(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("lulu_meta_install", _INSTALLER)
    assert spec is not None
    assert spec.loader is not None
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)

    target = tmp_path / "lulu-dev-workflow"
    installer.copy_skill_files(_WORKFLOW, target)

    installed_ask = target / "shared" / "references" / "ask-protocol.md"
    assert installed_ask.is_file()
    assert installed_ask.read_text(encoding="utf-8") == _SHARED_ASK.read_text(
        encoding="utf-8",
    )

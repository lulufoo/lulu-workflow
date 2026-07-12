#!/usr/bin/env python3
"""K3-c gate: four intent_gap profiles × chapter-anchored EvalTarget B.

For each of plan / design / arch / blueprint:

1. dimension-def binds ``intent_gap_probes``
2. a chapter-anchored B yields non-empty intent units via ``eval_target_units``
   (option 1 — units from B only; no compose sidecars)

Prefers live sim docs under repo ``.cache/`` when present; otherwise uses
committed fixtures under ``fixtures/intent_gap_chapter_b/``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_target_units as etu  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]
_WORKFLOW = _REPO / "lulu-dev-workflow"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "intent_gap_chapter_b"

# profile_id → (dimension-def relative path, preferred cache B, fixture B)
_PROFILES = {
    "lulu-plan": (
        "lulu-plan/dimension-defs/solution-quality.json",
        _REPO / ".cache/plan-init-sim-builders-entry/revision1/tech-doc.md",
        _FIXTURES / "plan-doc.md",
    ),
    "lulu-design": (
        "lulu-design/dimension-defs/solution-quality.json",
        None,  # no chapter-anchored design sim yet
        _FIXTURES / "design-doc.md",
    ),
    "lulu-arch": (
        "lulu-arch/dimension-defs/arch-quality.json",
        _REPO / ".cache/arch-init-sim-plan-task/revision1/arch-doc.md",
        _FIXTURES / "arch-doc.md",
    ),
    "lulu-blueprint": (
        "lulu-blueprint/dimension-defs/blueprint-quality.json",
        None,
        _FIXTURES / "blueprint-doc.md",
    ),
}


def _resolve_b(preferred: Path | None, fixture: Path) -> Path:
    if preferred is not None and preferred.is_file():
        text = preferred.read_text(encoding="utf-8")
        if etu.detect_shape(text) == "chapter":
            return preferred
    assert fixture.is_file(), f"missing fixture B: {fixture}"
    return fixture


@pytest.mark.parametrize("profile_id", sorted(_PROFILES))
def test_intent_gap_dimension_bound(profile_id: str) -> None:
    rel, _, _ = _PROFILES[profile_id]
    path = _WORKFLOW / rel
    assert path.is_file(), path
    data = json.loads(path.read_text(encoding="utf-8"))
    method = data.get("method") or {}
    source = method.get("source") or {}
    assert method.get("kind") == "builtin"
    assert source.get("procedure_id") == "intent_gap_probes"
    assert data.get("eval_target", {}).get("path") == "{compose_doc}"


@pytest.mark.parametrize("profile_id", sorted(_PROFILES))
def test_intent_gap_chapter_b_nonempty_units(profile_id: str) -> None:
    _, preferred, fixture = _PROFILES[profile_id]
    b_path = _resolve_b(preferred, fixture)
    view = etu.units_from_eval_target(b_path.read_text(encoding="utf-8"))
    assert view["shape"] == "chapter", (profile_id, b_path, view["shape"])
    assert view["empty"] is False, (profile_id, b_path)
    assert len(view["containers"]) >= 1
    total_units = sum(len(c["units"]) for c in view["containers"])
    assert total_units >= 1
    # Chapter-path helpers used by probe SKILL
    first_id = view["containers"][0]["id"]
    hints = etu.severity_hints_chapter(view, first_id)
    assert hints["is_first"] is True
    if len(view["containers"]) > 1:
        second = view["containers"][1]["id"]
        prior = etu.prior_container_units(view, second)
        assert prior


def test_four_profiles_cover_intent_gap_set() -> None:
    assert set(_PROFILES) == {
        "lulu-plan",
        "lulu-design",
        "lulu-arch",
        "lulu-blueprint",
    }

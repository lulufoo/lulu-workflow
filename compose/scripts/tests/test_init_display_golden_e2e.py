#!/usr/bin/env python3
"""Semi-real Init e2e + golden: five display_layer profiles.

Committed fixtures under ``fixtures/init_display_golden/{profile}/revision1``:

- ``lulu-plan`` / ``lulu-arch``: copied from Init sims (validate-green)
- ``lulu-design`` / ``lulu-spec`` / ``lulu-blueprint``: minimal generated revisions
  that pass ``validate_init_artifacts`` against live local registries

This is the mechanical half of the K3-b/b' gate (golden + validate). It does
**not** replace a live Initializing agent session (Step 5 prose authorship).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from bootstrap import refresh_compose_import_paths  # noqa: E402

refresh_compose_import_paths()

from init_compose_validation import validate_init_artifacts  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN_ROOT = Path(__file__).resolve().parent / "fixtures" / "init_display_golden"
_MANIFEST = json.loads((_GOLDEN_ROOT / "MANIFEST.json").read_text(encoding="utf-8"))

_PROFILES = {
    "lulu-plan": "tech-doc.md",
    "lulu-arch": "arch-doc.md",
    "lulu-design": "design-doc.md",
    "lulu-spec": "product-doc.md",
    "lulu-blueprint": "blueprint-doc.md",
}


def _revision(profile_id: str) -> Path:
    return _GOLDEN_ROOT / profile_id / "revision1"


def _compose_doc(profile_id: str) -> Path:
    return _revision(profile_id) / _PROFILES[profile_id]


@pytest.mark.parametrize("profile_id", sorted(_PROFILES))
def test_golden_manifest_lists_profile(profile_id: str) -> None:
    assert profile_id in _MANIFEST["profiles"]
    assert _MANIFEST["profiles"][profile_id]["doc"] == _PROFILES[profile_id]


@pytest.mark.parametrize("profile_id", sorted(_PROFILES))
def test_golden_revision_validate_init_artifacts(profile_id: str) -> None:
    rev = _revision(profile_id)
    doc = _compose_doc(profile_id)
    assert rev.is_dir(), rev
    assert doc.is_file(), doc
    error = validate_init_artifacts(rev, doc, _REPO, profile_id)
    assert error is None, f"{profile_id}: {error}"


@pytest.mark.parametrize("profile_id", sorted(_PROFILES))
def test_golden_compose_doc_chapter_units_nonempty(profile_id: str) -> None:
    eval_scripts = _REPO / "lulu-dev-workflow" / "eval" / "scripts"
    sys.path.insert(0, str(eval_scripts))
    import eval_target_units as etu  # noqa: E402

    view = etu.units_from_eval_target(_compose_doc(profile_id).read_text(encoding="utf-8"))
    assert view["shape"] == "chapter", (profile_id, view["shape"])
    assert view["empty"] is False
    assert len(view["containers"]) >= 1


@pytest.mark.parametrize("profile_id", ["lulu-plan", "lulu-arch"])
def test_sim_sourced_golden_has_facts_and_chapters_sidecars(profile_id: str) -> None:
    rev = _revision(profile_id)
    assert (rev / "_facts.json").is_file()
    assert (rev / "_chapters.json").is_file()
    facts = json.loads((rev / "_facts.json").read_text(encoding="utf-8"))
    chapters = json.loads((rev / "_chapters.json").read_text(encoding="utf-8"))
    assert isinstance(facts, list) and len(facts) >= 1
    assert isinstance(chapters, list) and len(chapters) >= 1
    # Sim goldens should keep human-authored prose (not the minimal template sentence).
    body_files = list(rev.glob("_body-*.txt"))
    assert body_files
    joined = "\n".join(p.read_text(encoding="utf-8") for p in body_files)
    assert "golden minimal" not in joined.lower()


def test_five_profiles_cover_k3_gate_set() -> None:
    assert set(_PROFILES) == {
        "lulu-plan",
        "lulu-arch",
        "lulu-design",
        "lulu-spec",
        "lulu-blueprint",
    }

#!/usr/bin/env python3
"""Tests for one ``lens`` per fact."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_COMPOSE = Path(__file__).resolve().parents[2]
_FACTS = _COMPOSE / "scripts" / "facts"
sys.path.insert(0, str(_COMPOSE / "scripts" / "_kernel"))
sys.path.insert(0, str(_FACTS))

from workflow_paths import seed_revision_profile_pointer  # noqa: E402
from facts_schema import validate_facts  # noqa: E402
from execution_state_schema import execution_dir  # noqa: E402
from init_working_helpers import seed_execution_revision  # noqa: E402

_INTAKE_CTL = (
    _COMPOSE / "fact-intake-runner" / "scripts" / "fact_intake_disposition_control.py"
)
_REPO = _COMPOSE.parent


def _revision(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir(parents=True, exist_ok=True)
    seed_revision_profile_pointer(rev)
    seed_execution_revision(rev, state="Inductive")
    return rev


def _carried(lens: str | None, fact_id: str = "F-1") -> dict:
    fact: dict = {
        "id": fact_id,
        "text": "x",
        "derivation": {"disposition": "carried", "upstream_ref": ["doc#1"]},
        "origin": {"type": "seed", "ref": ["doc"]},
    }
    if lens is not None:
        fact["lens"] = lens
    return fact


def _quarantined(fact_id: str = "F-1") -> dict:
    return {
        "id": fact_id,
        "text": "should carry",
        "derivation": {"disposition": "quarantined", "upstream_ref": ["doc#a"]},
    }


def test_validate_accepts_lens_and_omitted_lens():
    facts = [{"id": "F-1", "text": "one", "lens": "CTX"}, _quarantined("F-2")]
    assert validate_facts(facts, allowed_lenses=["CTX"]) == []


def test_carried_without_lens_is_rejected():
    errors = validate_facts([_carried(None)], allowed_lenses=["CTX"])
    assert any("carried requires lens" in e for e in errors)


def _run_patch(cmd: str, rev: Path, lens: str, tmp_path: Path):
    patch = {
        "version": "1",
        "ops": [{"op": "promote", "fact_id": "F-1", "lens": lens}],
    }
    patch_path = tmp_path / "patch.json"
    patch_path.write_text(json.dumps(patch), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(_INTAKE_CTL),
            cmd,
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--patch-file",
            str(patch_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_intake_patch_apply_persists_lens(tmp_path: Path):
    rev = _revision(tmp_path)
    facts_path = execution_dir(rev) / "_facts.json"
    other = {
        "id": "F-2",
        "text": "x",
        "lens": "GO",
        "derivation": {"disposition": "carried", "upstream_ref": ["doc#1"]},
        "origin": {"type": "seed", "ref": ["doc"]},
    }
    facts_path.write_text(json.dumps([_quarantined(), other]), encoding="utf-8")
    accepted = _run_patch("disposition-patch-apply", rev, "CTX", tmp_path)
    assert accepted.returncode == 0, accepted.stderr
    stored = {
        f["id"]: f.get("lens") for f in json.loads(facts_path.read_text("utf-8"))
    }
    assert stored == {"F-1": "CTX", "F-2": "GO"}


def _fact_production_module():
    for sub in ("scripts", "scripts/inductive", "fact-store-runner/scripts"):
        sys.path.insert(0, str(_COMPOSE / sub))
    import fact_production_control as fpc  # noqa: WPS433

    return fpc


def test_entry_facts_requires_lens(tmp_path: Path, monkeypatch):
    fpc = _fact_production_module()
    monkeypatch.setattr(fpc, "_allowed_lenses", lambda *_a, **_k: None)
    with pytest.raises(ValueError, match="lens must be a non-empty string"):
        fpc._entry_facts(
            [{"text": "new"}],
            facts_before=[],
            origin_ref=["O-1"],
            slice_dir=tmp_path,
        )
    facts, ids, _ = fpc._entry_facts(
        [{"text": "new", "lens": "GO"}],
        facts_before=[],
        origin_ref=["O-1"],
        slice_dir=tmp_path,
    )
    assert ids == ["F-1"]
    assert facts[0]["lens"] == "GO"

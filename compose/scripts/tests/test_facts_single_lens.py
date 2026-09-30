#!/usr/bin/env python3
"""Tests for the one-lens-per-fact rule on ``_facts.json`` lens tags."""

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
from facts_schema import load_facts, save_facts, validate_facts  # noqa: E402
from execution_state_schema import execution_dir  # noqa: E402
from init_working_helpers import seed_execution_revision  # noqa: E402

_CTL = _FACTS / "facts_control.py"
_INTAKE_CTL = (
    _COMPOSE / "fact-intake-runner" / "scripts" / "fact_intake_disposition_control.py"
)
_REPO = _COMPOSE.parent

_MULTI_ERROR = "facts[0].lens_tags must hold exactly one lens (got 2)"


def _revision(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir(parents=True, exist_ok=True)
    seed_revision_profile_pointer(rev)
    seed_execution_revision(rev, state="Inductive")
    return rev


def _carried(tags: list[str], fact_id: str = "F-1") -> dict:
    return {
        "id": fact_id,
        "text": "x",
        "lens_tags": tags,
        "derivation": {"disposition": "carried", "upstream_ref": ["doc#1"]},
        "origin": {"type": "seed", "ref": ["doc"]},
    }


def _quarantined(fact_id: str = "F-1") -> dict:
    return {
        "id": fact_id,
        "text": "should carry",
        "lens_tags": [],
        "derivation": {"disposition": "quarantined", "upstream_ref": ["doc#a"]},
    }


def _run_control(cmd: str, rev: Path, facts_file: Path | None = None):
    args = [
        sys.executable,
        str(_CTL),
        cmd,
        "--revision-dir",
        str(rev),
        "--project-root",
        str(_REPO),
    ]
    if facts_file is not None:
        args += ["--facts-file", str(facts_file)]
    return subprocess.run(args, check=False, capture_output=True, text=True)


def test_validate_rejects_multi_tag():
    facts = [{"id": "F-1", "text": "two", "lens_tags": ["CTX", "GO"]}]
    assert validate_facts(facts, allowed_lenses=["CTX", "GO"]) == [_MULTI_ERROR]


def test_validate_accepts_one_tag_and_empty_tags():
    facts = [{"id": "F-1", "text": "one", "lens_tags": ["CTX"]}, _quarantined("F-2")]
    assert validate_facts(facts, allowed_lenses=["CTX"]) == []


def test_carried_with_empty_tags_still_rejected():
    errors = validate_facts([_carried([])], allowed_lenses=["CTX"])
    assert any("carried requires non-empty lens_tags" in e for e in errors)


def test_save_facts_rejects_multi_tag(tmp_path: Path):
    path = tmp_path / "_facts.json"
    facts = [{"id": "F-1", "text": "two", "lens_tags": ["CTX", "GO"]}]
    with pytest.raises(ValueError, match="exactly one lens"):
        save_facts(path, facts, allowed_lenses=["CTX", "GO"])
    assert not path.exists()


def test_load_facts_reads_legacy_multi_tag_as_first_tag(tmp_path: Path):
    path = tmp_path / "_facts.json"
    raw = [{"id": "F-1", "text": "legacy", "lens_tags": ["GO", "CTX"]}]
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert load_facts(path)[0]["lens_tags"] == ["GO"]
    assert json.loads(path.read_text(encoding="utf-8")) == raw

    save_facts(path, load_facts(path), allowed_lenses=["CTX", "GO"])
    assert json.loads(path.read_text(encoding="utf-8"))[0]["lens_tags"] == ["GO"]


def test_control_write_rejects_multi_tag(tmp_path: Path):
    rev = _revision(tmp_path)
    facts_path = execution_dir(rev) / "_facts.json"
    multi = tmp_path / "multi.json"
    multi.write_text(json.dumps([_carried(["CTX", "GO"])]), encoding="utf-8")
    rejected = _run_control("write", rev, multi)
    assert rejected.returncode != 0
    assert "exactly one lens" in rejected.stderr
    assert not facts_path.exists()

    single = tmp_path / "single.json"
    single.write_text(json.dumps([_carried(["CTX"])]), encoding="utf-8")
    assert _run_control("write", rev, single).returncode == 0


def test_control_validate_rejects_multi_tag(tmp_path: Path):
    rev = _revision(tmp_path)
    (execution_dir(rev) / "_facts.json").write_text(
        json.dumps([_carried(["CTX", "GO"])]), encoding="utf-8"
    )
    rejected = _run_control("validate", rev)
    assert rejected.returncode != 0
    assert "exactly one lens" in rejected.stderr


def _run_patch(cmd: str, rev: Path, tags: list[str], tmp_path: Path):
    patch = {
        "version": "1",
        "ops": [{"op": "promote", "fact_id": "F-1", "lens_tags": tags}],
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


@pytest.mark.parametrize("cmd", ["disposition-patch-validate", "disposition-patch-apply"])
def test_intake_patch_rejects_multi_tag_op(tmp_path: Path, cmd: str):
    rev = _revision(tmp_path)
    facts_path = execution_dir(rev) / "_facts.json"
    facts_path.write_text(json.dumps([_quarantined()]), encoding="utf-8")
    before = facts_path.read_text(encoding="utf-8")
    rejected = _run_patch(cmd, rev, ["CTX", "GO"], tmp_path)
    assert rejected.returncode != 0
    assert "exactly one lens" in rejected.stderr
    assert facts_path.read_text(encoding="utf-8") == before
    assert _run_patch(cmd, rev, ["CTX"], tmp_path).returncode == 0


def test_intake_patch_apply_persists_legacy_multi_tag_as_first_tag(tmp_path: Path):
    rev = _revision(tmp_path)
    facts_path = execution_dir(rev) / "_facts.json"
    legacy = _carried(["GO", "CTX"], "F-2")
    facts_path.write_text(json.dumps([_quarantined(), legacy]), encoding="utf-8")
    accepted = _run_patch("disposition-patch-apply", rev, ["CTX"], tmp_path)
    assert accepted.returncode == 0, accepted.stderr
    stored = {f["id"]: f["lens_tags"] for f in json.loads(facts_path.read_text("utf-8"))}
    assert stored == {"F-1": ["CTX"], "F-2": ["GO"]}


def _fact_production_module():
    for sub in ("scripts", "scripts/inductive", "fact-store-runner/scripts"):
        sys.path.insert(0, str(_COMPOSE / sub))
    import fact_production_control as fpc  # noqa: WPS433

    return fpc


def test_entry_facts_rejects_multi_tag_entry(tmp_path: Path, monkeypatch):
    fpc = _fact_production_module()
    monkeypatch.setattr(fpc, "_allowed_lenses", lambda *_a, **_k: None)
    with pytest.raises(ValueError, match="exactly one lens"):
        fpc._entry_facts(
            [{"text": "new", "lens_tags": ["CTX", "GO"]}],
            facts_before=[],
            origin_ref=["O-1"],
            slice_dir=tmp_path,
        )
    facts, ids, _ = fpc._entry_facts(
        [{"text": "new", "lens_tags": ["GO"]}],
        facts_before=[],
        origin_ref=["O-1"],
        slice_dir=tmp_path,
    )
    assert ids == ["F-1"]
    assert facts[0]["lens_tags"] == ["GO"]

#!/usr/bin/env python3
"""Tests for the opt-in single-lens rule on ``_facts.json`` lens tags."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_FACTS = Path(__file__).resolve().parent.parent / "facts"
_KERNEL = Path(__file__).resolve().parent.parent / "_kernel"
sys.path.insert(0, str(_KERNEL))
sys.path.insert(0, str(_FACTS))

from workflow_paths import seed_revision_profile_pointer  # noqa: E402
from facts_schema import save_facts, validate_facts  # noqa: E402
from execution_state_schema import execution_dir  # noqa: E402
from init_working_helpers import seed_execution_revision  # noqa: E402

_CTL = _FACTS / "facts_control.py"
_REPO = Path(__file__).resolve().parents[4]


def _revision(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir(parents=True, exist_ok=True)
    seed_revision_profile_pointer(rev)
    seed_execution_revision(rev, state="Inductive")
    return rev


def _carried(tags: list[str]) -> list[dict]:
    return [
        {
            "id": "F-1",
            "text": "x",
            "lens_tags": tags,
            "derivation": {"disposition": "carried", "upstream_ref": ["doc#1"]},
            "origin": {"type": "seed", "ref": ["doc"]},
        }
    ]


def _run(cmd: str, rev: Path, *extra: str, facts_file: Path | None = None):
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
    return subprocess.run(
        [*args, *extra], check=False, capture_output=True, text=True
    )


def test_multi_tag_rejected_only_when_enabled():
    facts = [{"id": "F-1", "text": "two", "lens_tags": ["CTX", "GO"]}]
    lenses = ["CTX", "GO"]
    assert validate_facts(facts, allowed_lenses=lenses) == []
    errors = validate_facts(facts, allowed_lenses=lenses, single_lens=True)
    assert errors == ["facts[0].lens_tags must hold exactly one lens (got 2)"]


def test_one_tag_and_empty_tags_accepted():
    facts = [
        {"id": "F-1", "text": "one", "lens_tags": ["CTX"]},
        {
            "id": "F-2",
            "text": "quarantined",
            "lens_tags": [],
            "derivation": {"disposition": "quarantined", "upstream_ref": ["doc#1"]},
        },
    ]
    assert validate_facts(facts, allowed_lenses=["CTX"], single_lens=True) == []


def test_carried_with_empty_tags_still_rejected():
    errors = validate_facts(_carried([]), allowed_lenses=["CTX"], single_lens=True)
    assert any("carried requires non-empty lens_tags" in e for e in errors)


def test_save_facts_rejects_multi_tag_only_when_enabled(tmp_path: Path):
    path = tmp_path / "_facts.json"
    facts = [{"id": "F-1", "text": "two", "lens_tags": ["CTX", "GO"]}]
    with pytest.raises(ValueError, match="exactly one lens"):
        save_facts(path, facts, allowed_lenses=["CTX", "GO"], single_lens=True)
    assert not path.exists()
    save_facts(path, facts, allowed_lenses=["CTX", "GO"])
    assert path.is_file()


def test_control_write_flag(tmp_path: Path):
    rev = _revision(tmp_path)
    facts_path = execution_dir(rev) / "_facts.json"
    multi = tmp_path / "multi.json"
    multi.write_text(json.dumps(_carried(["CTX", "GO"])), encoding="utf-8")
    rejected = _run("write", rev, "--single-lens", facts_file=multi)
    assert rejected.returncode != 0
    assert "exactly one lens" in rejected.stderr
    assert not facts_path.exists()

    single = tmp_path / "single.json"
    single.write_text(json.dumps(_carried(["CTX"])), encoding="utf-8")
    accepted = _run("write", rev, "--single-lens", facts_file=single)
    assert accepted.returncode == 0, accepted.stderr


def test_control_validate_flag(tmp_path: Path):
    rev = _revision(tmp_path)
    (execution_dir(rev) / "_facts.json").write_text(
        json.dumps(_carried(["CTX", "GO"])), encoding="utf-8"
    )
    relaxed = _run("validate", rev, "--require-derivation")
    assert relaxed.returncode == 0, relaxed.stderr
    strict = _run("validate", rev, "--require-derivation", "--single-lens")
    assert strict.returncode != 0
    assert "exactly one lens" in strict.stderr


_INTAKE_CTL = (
    Path(__file__).resolve().parents[2]
    / "fact-intake-runner"
    / "scripts"
    / "fact_intake_disposition_control.py"
)


def _quarantined_fact() -> list[dict]:
    return [
        {
            "id": "F-1",
            "text": "should carry",
            "lens_tags": [],
            "derivation": {"disposition": "quarantined", "upstream_ref": ["doc#a"]},
        }
    ]


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
    facts_path.write_text(json.dumps(_quarantined_fact()), encoding="utf-8")
    before = facts_path.read_text(encoding="utf-8")
    rejected = _run_patch(cmd, rev, ["CTX", "GO"], tmp_path)
    assert rejected.returncode != 0
    assert "exactly one lens" in rejected.stderr
    assert facts_path.read_text(encoding="utf-8") == before
    accepted = _run_patch(cmd, rev, ["CTX"], tmp_path)
    assert accepted.returncode == 0, accepted.stderr


def test_intake_patch_ignores_untouched_multi_tag_facts(tmp_path: Path):
    rev = _revision(tmp_path)
    legacy = {
        "id": "F-2",
        "text": "legacy multi-tag",
        "lens_tags": ["CTX", "GO"],
        "derivation": {"disposition": "carried", "upstream_ref": ["doc#b"]},
    }
    facts_path = execution_dir(rev) / "_facts.json"
    facts_path.write_text(
        json.dumps([*_quarantined_fact(), legacy]), encoding="utf-8"
    )
    accepted = _run_patch("disposition-patch-apply", rev, ["CTX"], tmp_path)
    assert accepted.returncode == 0, accepted.stderr


def _fact_production_module():
    compose = Path(__file__).resolve().parents[2]
    for sub in ("scripts", "scripts/inductive", "fact-store-runner/scripts"):
        sys.path.insert(0, str(compose / sub))
    import fact_production_control as fpc  # noqa: WPS433

    return fpc


def test_entry_facts_checks_only_new_entries(tmp_path: Path, monkeypatch):
    fpc = _fact_production_module()
    monkeypatch.setattr(fpc, "_allowed_lenses", lambda *_a, **_k: None)
    legacy = [
        {
            "id": "F-1",
            "text": "legacy multi-tag",
            "lens_tags": ["CTX", "GO"],
            "origin": {"type": "seed", "ref": ["doc"]},
        }
    ]
    with pytest.raises(ValueError, match="exactly one lens"):
        fpc._entry_facts(
            [{"text": "new", "lens_tags": ["CTX", "GO"]}],
            facts_before=legacy,
            origin_ref=["O-1"],
            slice_dir=tmp_path,
        )
    facts, ids, _ = fpc._entry_facts(
        [{"text": "new", "lens_tags": ["GO"]}],
        facts_before=legacy,
        origin_ref=["O-1"],
        slice_dir=tmp_path,
    )
    assert ids == ["F-2"]
    assert facts[0]["lens_tags"] == ["CTX", "GO"]

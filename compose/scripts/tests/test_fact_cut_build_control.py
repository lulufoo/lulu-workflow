#!/usr/bin/env python3
"""Tests for merged fact-cut context and seed+disposition write."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_FACTS = _SCRIPTS / "facts"
_KERNEL = _SCRIPTS / "_kernel"
_CUT = (
    _SCRIPTS.parent
    / "fact-intake-runner"
    / "fact-cut-runner"
    / "scripts"
    / "fact_cut_build_control.py"
)
sys.path.insert(0, str(_KERNEL))
sys.path.insert(0, str(_FACTS))

from facts_schema import validate_facts  # noqa: E402
from init_working_helpers import seed_execution_revision  # noqa: E402
from workflow_paths import seed_revision_profile_pointer  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]
_CTL = _FACTS / "facts_control.py"


def _revision(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir(parents=True, exist_ok=True)
    seed_revision_profile_pointer(rev)
    seed_execution_revision(rev, state="FactIntake")
    return rev


def _run_context(rev: Path) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(_CUT),
            "context",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_cut_context_is_closed_packet(tmp_path: Path):
    payload = _run_context(_revision(tmp_path))
    assert payload["ok"] is True
    assert payload["command"] == "context"
    assert payload["facts_path"].endswith("_facts.json")
    assert payload["facts"] == []
    assert "consume_policy_rule_ids" not in payload
    assert "section_order" not in payload
    assert payload["consume_policy_rules"]
    lenses = {item["lens"]: item for item in payload["lens_registry"]}
    assert "CTX" in lenses
    assert lenses["CTX"]["intent"]
    assert "intent_boundary" in lenses["CTX"]


def test_validate_seed_origin_without_intake_structure():
    facts = [
        {
            "id": "F-1",
            "text": "atom",
            "lens": "CTX",
            "origin": {"type": "seed", "ref": ["doc"]},
            "derivation": {
                "disposition": "carried",
                "upstream_ref": ["doc#1"],
            },
        }
    ]
    assert (
        validate_facts(
            facts,
            allowed_lenses=["CTX"],
            require_derivation=True,
            require_seed_origin=True,
        )
        == []
    )
    bad = [
        {
            **facts[0],
            "origin": {"type": "derived", "ref": ["F-0"]},
        }
    ]
    errors = validate_facts(
        bad,
        allowed_lenses=["CTX"],
        require_derivation=True,
        require_seed_origin=True,
    )
    assert any("must be 'seed'" in item for item in errors)


def test_write_seed_and_disposition_with_require_seed_origin(tmp_path: Path):
    rev = _revision(tmp_path)
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "atom from source",
                    "lens": "CTX",
                    "origin": {"type": "seed", "ref": ["source.md"]},
                    "derivation": {
                        "disposition": "carried",
                        "upstream_ref": ["source.md#1"],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--facts-file",
            str(facts_file),
            "--require-seed-origin",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr
    validate = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "validate",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--require-derivation",
            "--require-seed-origin",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert validate.returncode == 0, validate.stderr

#!/usr/bin/env python3
"""Tests for stateless inductive shape perception control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SHAPE_CTL = _INDUCTIVE_DIR / "inductive_shape_control.py"
_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

from compose_state_lock import canonical_digest  # noqa: E402


def _run_shape(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [
            sys.executable,
            str(_SHAPE_CTL),
            "--out-dir",
            str(out_dir),
            "--project-root",
            str(out_dir),
            *args,
        ],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_shape_control_writes_nothing_and_missing_facts_are_empty(tmp_path: Path) -> None:
    before = _file_snapshot(tmp_path)
    code, payload = _run_shape(tmp_path)
    assert code == 0, payload
    after = _file_snapshot(tmp_path)
    assert after == before
    assert payload.get("facts_count") == 0
    assert payload.get("facts_digest") == canonical_digest([])
    assert payload.get("lenses") == []
    assert payload.get("lenses_with_facts") == []
    assert payload.get("lenses_without_facts") == []
    assert payload.get("open_count") == 0
    perception = payload.get("perception")
    assert isinstance(perception, str) and perception.strip()


def test_shape_control_perceive_splits_lenses_and_counts_opens(tmp_path: Path) -> None:
    (tmp_path / "_facts.json").write_text(
        json.dumps(
            [
                {"id": "F-1", "text": "intent is logged", "lens_tags": ["I"]},
                {"id": "F-2", "text": "untagged", "lens_tags": []},
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "section-registry.json").write_text(
        json.dumps(
            {
                "section_order": ["I", "ST"],
                "sections": {"I": {"heading": "Intent"}, "ST": {"heading": "Structure"}},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "inductive-opens.json").write_text(
        json.dumps(
            [
                {
                    "id": "O-1",
                    "status": "open",
                    "source": {"actor": "human", "means": "direct"},
                    "question": "What is missing?",
                    "basis": "Dialogue",
                    "blocking": True,
                    "lens": "I",
                },
                {
                    "id": "O-2",
                    "status": "settled",
                    "source": {"actor": "human", "means": "direct"},
                    "question": "Already closed",
                    "basis": "Landed",
                    "blocking": False,
                    "lens": "I",
                    "resolved_by": ["F-1"],
                },
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    before = _file_snapshot(tmp_path)
    code, payload = _run_shape(tmp_path, "perceive")
    assert code == 0, payload
    assert _file_snapshot(tmp_path) == before
    assert payload.get("facts_count") == 2
    assert payload.get("facts_digest") == canonical_digest(
        json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    )
    assert payload.get("lenses") == ["I", "ST"]
    assert payload.get("lenses_with_facts") == ["I"]
    assert payload.get("lenses_without_facts") == ["ST"]
    assert payload.get("open_count") == 1
    assert isinstance(payload.get("perception"), str) and payload["perception"].strip()

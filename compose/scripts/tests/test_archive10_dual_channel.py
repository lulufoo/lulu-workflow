#!/usr/bin/env python3
"""Unified narrative-arc write (no viewer mount)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_REPO = Path(__file__).resolve().parents[4]
_SCRIPTS = _COMPOSE / "scripts"
_WRITING = _SCRIPTS / "writing"
_NARRATIVE = _COMPOSE / "narrative-arc-runner" / "scripts"
_ARC_CTL = _NARRATIVE / "narrative_arc_control.py"
_ARC_BUILD = _NARRATIVE / "narrative_arc_build_control.py"

_KERNEL = _SCRIPTS / "_kernel"
for _p in (_WRITING, _WRITING / "schema", _NARRATIVE, _SCRIPTS, _KERNEL):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from compose_state_lock import canonical_digest  # noqa: E402
from narrative_arc_schema import save_narrative_arc  # noqa: E402
from workflow_paths import seed_revision_profile_pointer  # noqa: E402


def _run(cmd: list[str], *, cwd: Path | None = None):
    import subprocess

    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_ready_arc() -> dict:
    return {
        "version": "1",
        "kind": "narrative-arc",
        "status": "write_ready",
        "leaves": [
            {
                "id": "L1",
                "title": "Leaf",
                "fact_ids": ["F-1"],
                "chapters": [{"lens": "CTX", "fact_ids": ["F-1"]}],
            }
        ],
    }


def _facts_file(slice_dir: Path) -> None:
    (slice_dir / "_facts.json").write_text(
        json.dumps(
            {
                "version": "1",
                "facts": [
                    {
                        "id": "F-1",
                        "text": "fact",
                        "lens_tags": ["CTX"],
                        "source": "test",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_unified_write_digest_and_backup(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    slice_dir = rev / "execution"
    slice_dir.mkdir(parents=True, exist_ok=True)
    _facts_file(slice_dir)
    out = slice_dir / "_narrative-arc.collab.json"
    save_narrative_arc(out, _write_ready_arc(), facts=None, allowed_lenses=None)
    candidate = tmp_path / "cand.json"
    arc = _write_ready_arc()
    arc["leaves"][0]["title"] = "Leaf v2"
    candidate.write_text(json.dumps(arc, ensure_ascii=False), encoding="utf-8")
    digest = canonical_digest(arc)
    bad = _run(
        [
            sys.executable,
            str(_ARC_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--output-path",
            "_narrative-arc.collab.json",
            "--file",
            str(candidate),
            "--digest",
            "deadbeef",
            "--require-write-ready",
            "--skip-facts",
        ]
    )
    assert bad.returncode != 0
    assert out.read_text(encoding="utf-8").count("Leaf v2") == 0

    ok = _run(
        [
            sys.executable,
            str(_ARC_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--output-path",
            "_narrative-arc.collab.json",
            "--file",
            str(candidate),
            "--digest",
            digest,
            "--require-write-ready",
            "--skip-facts",
        ]
    )
    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    assert payload["backup"]
    assert "Leaf v2" in out.read_text(encoding="utf-8")


def test_build_validate_candidate_no_target_flag(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    # Minimal: missing facts → fail without --target
    result = _run(
        [
            sys.executable,
            str(_ARC_BUILD),
            "validate-candidate",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--cycle-type",
            "feature",
            "--file",
            str(tmp_path / "missing.json"),
        ]
    )
    assert result.returncode != 0
    assert "--target" not in result.stdout

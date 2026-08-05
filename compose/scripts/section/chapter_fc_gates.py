#!/usr/bin/env python3
"""Hard gates for Init chapter write artifacts.

Init Write persists ``_body-{cid}.txt`` only. ``_derive-*.json`` and
body↔``form.structure`` probes are not Init hard gates (archive-7.0).

Shared by ``chapter_write_state_control.complete`` and
``init_compose_validation`` (Step 5).
"""

from __future__ import annotations

from pathlib import Path

from chapter_artifact_paths import chapter_body_path


def check_chapter_write_artifacts(revision_dir: Path, cid: str) -> list[str]:
    """Per-chapter write gate: non-empty body only."""
    errors: list[str] = []
    body = chapter_body_path(revision_dir, cid)
    if not body.is_file():
        errors.append(f"missing body: {body.name}")
        return errors
    body_text = body.read_text(encoding="utf-8")
    if not body_text.strip():
        errors.append(f"empty body: {body.name}")
    return errors

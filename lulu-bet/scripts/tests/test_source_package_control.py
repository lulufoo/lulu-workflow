#!/usr/bin/env python3
"""Tests for lulu-bet source-package delivery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from source_package_control import deliver  # noqa: E402

from cycle_delivered_refs import load_delivered_refs_file  # noqa: E402


def test_deliver_commits_single_l1_source_package(tmp_path: Path) -> None:
    root = tmp_path / ".cache/cursor/lulu-dev-workflow/feature-bet/lulu-bet"
    root.mkdir(parents=True)
    (root / "decision-fact.json").write_text('{"version": 1, "gates": {}}\n')
    (root / "session-state.md").write_text(
        "---\ncurrent_state: InProgress\n---\n",
        encoding="utf-8",
    )

    source_path = deliver(root, cycle_id="feature-bet", project_root=tmp_path)

    package = json.loads(source_path.read_text(encoding="utf-8"))
    assert package == {
        "version": 1,
        "holder_stage": "lulu-bet",
        "slices": [
            {
                "id": "L1",
                "title": "main",
                "source_path": "decision-fact.json",
                "source_id": "main",
            }
        ],
        "commit_status": "committed",
    }
    refs = load_delivered_refs_file("feature-bet", tmp_path)
    assert refs["entries"]["lulu-bet"]["path"] == str(source_path.resolve())
    assert refs["entries"]["lulu-bet"]["artifact"] == "source-package"
    assert "current_state: Completed" in (root / "session-state.md").read_text(
        encoding="utf-8"
    )

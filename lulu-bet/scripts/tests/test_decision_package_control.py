#!/usr/bin/env python3
"""Tests for lulu-bet decision-package delivery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_package_control import deliver  # noqa: E402

from cycle_delivered_refs import load_delivered_refs_file  # noqa: E402


def test_deliver_commits_decision_package(tmp_path: Path) -> None:
    root = tmp_path / ".cache/cursor/lulu-dev-workflow/feature-bet/lulu-bet"
    root.mkdir(parents=True)
    (root / "decision-doc.md").write_text("# Decision\n\nSettled.\n", encoding="utf-8")
    (root / "session-state.md").write_text(
        "---\ncurrent_state: InProgress\n---\n",
        encoding="utf-8",
    )
    (root / "source-package.json").write_text("{}\n", encoding="utf-8")

    package_path = deliver(root, cycle_id="feature-bet", project_root=tmp_path)

    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert package == {
        "version": 1,
        "status": "package_ready",
        "main": {

            "decision_doc_path": "decision-doc.md",
        },
        "slices": [],
    }
    refs = load_delivered_refs_file("feature-bet", tmp_path)
    assert refs["entries"]["lulu-bet"]["path"] == str(package_path.resolve())
    assert refs["entries"]["lulu-bet"]["artifact"] == "decision-package"
    assert package_path.name == "decision-package.json"
    assert not (root / "source-package.json").exists()
    assert "current_state: Completed" in (root / "session-state.md").read_text(
        encoding="utf-8"
    )


def test_deliver_requires_decision_doc(tmp_path: Path) -> None:
    root = tmp_path / "lulu-bet"
    root.mkdir(parents=True)
    (root / "session-state.md").write_text(
        "---\ncurrent_state: InProgress\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="decision-doc.md"):
        deliver(root, cycle_id="feature-bet", project_root=tmp_path)

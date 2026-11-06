#!/usr/bin/env python3
"""Topic Bet and Approach start on their own: neither needs the other."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_WORKFLOW = Path(__file__).resolve().parents[3]
_CACHE_ROOT = Path(".cache/cursor/lulu-workflow")
_OTHER = {"lulu-bet": "lulu-approach", "lulu-approach": "lulu-bet"}


@pytest.mark.parametrize("other_in_progress", [False, True], ids=["alone", "other-in-progress"])
@pytest.mark.parametrize("stage", ["lulu-bet", "lulu-approach"])
def test_topic_decision_starts_without_the_other(tmp_path: Path, stage: str, other_in_progress: bool) -> None:
    cycle_id = "topic-independent"
    cache = tmp_path / _CACHE_ROOT
    cycle = cache / cycle_id
    cycle.mkdir(parents=True)
    (cache / "cycles.json").write_text(json.dumps({cycle_id: {"name": "topic"}}))
    other_state = cycle / _OTHER[stage] / "session-state.md"
    if other_in_progress:
        other_state.parent.mkdir()
        other_state.write_text("---\ncurrent_state: Drafting\n---\n")
        (cycle / "cycle-state.json").write_text(json.dumps({"current_stage": _OTHER[stage]}))

    started = subprocess.run(
        [sys.executable, str(_WORKFLOW / "decision/scripts/dec_start.py"), "--project-root", str(tmp_path),
         "--cycle-id", cycle_id, "--constraints", str(_WORKFLOW / stage / "constraints-topic.json"),
         "--conversation-id", "conv-1"],
        cwd=tmp_path, env={**os.environ, "LULU_PLATFORM": "cursor"}, capture_output=True, text=True,
    )

    assert started.returncode == 0, started.stdout + started.stderr
    assert (cycle / stage / "gate-state.json").is_file()
    if other_in_progress:
        assert other_state.read_text() == "---\ncurrent_state: Drafting\n---\n"

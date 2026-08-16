#!/usr/bin/env python3
"""Tests for Open-point control CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_CTL = _INDUCTIVE_DIR / "open_point_control.py"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from compose_state_lock import canonical_digest  # noqa: E402
from open_point_store import add_opens  # noqa: E402


def _run(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [
            sys.executable,
            str(_CTL),
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


def _human_open(**overrides):
    base = {
        "question": "What is unresolved?",
        "basis": "Dialogue exposed a gap",
        "blocking": True,
        "source": {"actor": "human", "means": "direct"},
    }
    base.update(overrides)
    return base


def _detect_json(out_dir: Path, raw_candidates):
    facts_digest = canonical_digest([])
    lens_digest = canonical_digest([])
    opens_digest = canonical_digest([])
    return json.dumps(
        {
            "checked_lenses": ["I"],
            "facts_digest": facts_digest,
            "lens_digest": lens_digest,
            "opens_digest": opens_digest,
            "raw_candidates": raw_candidates,
            "expected_facts_digest": facts_digest,
            "expected_lens_digest": lens_digest,
            "expected_opens_digest": opens_digest,
        }
    )


def test_detect_context_refused_when_processing(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    code, payload = _run(tmp_path, "detect-context")
    assert code == 1
    assert payload["ok"] is False
    assert "idle" in payload["error"] or "processing" in payload["error"]


def test_add_opens_json_round_trip(tmp_path: Path):
    opens = [_human_open(), _human_open(question="second", blocking=False)]
    code, payload = _run(tmp_path, "add-opens", "--opens-json", json.dumps(opens))
    assert code == 0, payload
    assert payload["ok"] is True
    registered = payload.get("opens") or payload.get("added")
    assert [item["question"] for item in registered] == [
        "What is unresolved?",
        "second",
    ]
    assert [item["id"] for item in registered] == ["O-1", "O-2"]
    code, ctx = _run(tmp_path, "resolve-context")
    assert code == 0, ctx
    assert ctx["state"]["phase"] == "processing"
    assert ctx["state"]["active_open_id"] == "O-1"


def test_disposition_stale_digest_rejected(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    code, payload = _run(
        tmp_path,
        "defer-open",
        "--open-id",
        "O-1",
        "--note",
        "later",
        "--facts-digest",
        canonical_digest(["stale"]),
        "--open-digest",
        canonical_digest(["stale"]),
        "--batch-digest",
        canonical_digest(["stale"]),
    )
    assert code == 1
    assert payload == {"ok": False, "error": "stale"}


def test_check_close_is_predicate_only(tmp_path: Path):
    add_opens(tmp_path, opens=[], detect=json.loads(_detect_json(tmp_path, [])))
    code, payload = _run(tmp_path, "check-close", "--mode", "cleared")
    assert code == 0, payload
    assert payload["ok"] is True
    add_opens(tmp_path, opens=[
        {
            "question": "q",
            "basis": "b",
            "blocking": False,
            "source": {"actor": "human", "means": "direct"},
        }
    ])
    code, payload = _run(tmp_path, "check-close", "--mode", "hard-skip")
    assert code == 0, payload
    bundle_opens = json.loads(
        (tmp_path / "inductive-opens.json").read_text(encoding="utf-8")
    )
    assert any(item.get("status") == "open" for item in bundle_opens)
    state = json.loads(
        (tmp_path / "open-point-state.json").read_text(encoding="utf-8")
    )
    assert state["phase"] == "processing"


def test_check_close_cleared_confirm_requires_fresh_zero_result(tmp_path: Path):
    code, payload = _run(
        tmp_path,
        "add-opens",
        "--opens-json",
        "[]",
        "--detect-json",
        _detect_json(tmp_path, []),
    )
    assert code == 0, payload
    code, payload = _run(
        tmp_path, "check-close", "--mode", "cleared", "--confirm"
    )
    assert code == 0, payload
    assert payload["ok"] is True

    (tmp_path / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "moved"}], indent=2) + "\n",
        encoding="utf-8",
    )
    code, payload = _run(
        tmp_path, "check-close", "--mode", "cleared", "--confirm"
    )
    assert code == 1
    assert payload["ok"] is False

#!/usr/bin/env python3
"""Tests for Open-point control CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SCHEMA_DIR = _INDUCTIVE_DIR / "schema"
_CTL = _INDUCTIVE_DIR / "open_point_control.py"
sys.path.insert(0, str(_INDUCTIVE_DIR))
sys.path.insert(0, str(_SCHEMA_DIR))

from compose_state_lock import canonical_digest  # noqa: E402
from lens_frontier_schema import (  # noqa: E402
    default_lens_entry,
    lens_frontier_path,
    load_lens_frontier,
)
from open_point_store import add_opens, ensure_frontier, set_frontier  # noqa: E402

_REGISTRY = {
    "version": "1",
    "document_preamble": "test",
    "section_order": ["I"],
    "sections": {
        "I": {"heading": "Intent", "intent": "constraints", "presence": "required"}
    },
}
_KW = "## I\n\n| KW | x |\n|----|---|\n| KW0 | n |\n| KW1 | r |\n| KW3 | b |\n"


def _write_registry(out_dir: Path) -> None:
    (out_dir / "section-registry.json").write_text(
        json.dumps(_REGISTRY) + "\n", encoding="utf-8"
    )


def _write_kw(out_dir: Path) -> None:
    (out_dir / "section-kw-criteria.md").write_text(_KW, encoding="utf-8")


def _ready_cleared(out_dir: Path) -> None:
    _write_registry(out_dir)
    _write_kw(out_dir)
    ensure_frontier(out_dir)


def _run(out_dir: Path, *args: str, project_root: str | None = None) -> tuple[int, dict]:
    cmd = [sys.executable, str(_CTL), "--out-dir", str(out_dir)]
    if project_root is not None:
        cmd.extend(["--project-root", project_root])
    cmd.extend(args)
    res = subprocess.run(
        cmd,
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
        "lens": "I",
    }
    base.update(overrides)
    return base


def _lens_measurements(out_dir: Path, checked, raw_candidates):
    path = lens_frontier_path(out_dir)
    lenses = load_lens_frontier(path)["lenses"] if path.is_file() else {}
    hit = {
        str(item.get("lens", "")).strip().upper()
        for item in raw_candidates
        if isinstance(item, dict) and item.get("lens")
    }
    out = []
    for lens in checked:
        key = str(lens).strip().upper()
        entry = lenses.get(key) or default_lens_entry()
        start = int(entry.get("frontier_kw") or 0)
        out.append(
            {"lens": key, "start_kw": start, "gap_kw": start if key in hit else None}
        )
    return out


def _detect_json(out_dir: Path, raw_candidates):
    from open_point_store import frontier_digest  # noqa: WPS433

    facts = []
    if (out_dir / "_facts.json").is_file():
        facts = json.loads((out_dir / "_facts.json").read_text(encoding="utf-8"))
    lenses = []
    if (out_dir / "section-registry.json").is_file():
        lenses = json.loads((out_dir / "section-registry.json").read_text(encoding="utf-8"))
    opens = []
    if (out_dir / "inductive-opens.json").is_file():
        opens = json.loads((out_dir / "inductive-opens.json").read_text(encoding="utf-8"))
    facts_digest = canonical_digest(facts)
    lens_digest = canonical_digest(lenses)
    opens_digest = canonical_digest(opens)
    ensure_frontier(out_dir)
    frontier_d = frontier_digest(out_dir)
    checked = ["I"]
    return json.dumps(
        {
            "checked_lenses": checked,
            "facts_digest": facts_digest,
            "lens_digest": lens_digest,
            "opens_digest": opens_digest,
            "frontier_digest": frontier_d,
            "raw_candidates": raw_candidates,
            "expected_facts_digest": facts_digest,
            "expected_lens_digest": lens_digest,
            "expected_opens_digest": opens_digest,
            "expected_frontier_digest": frontier_d,
            "inert_means": ["intent", "scan"],
            "lens_measurements": _lens_measurements(out_dir, checked, raw_candidates),
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
    _ready_cleared(tmp_path)
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
            "lens": "I",
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
    _ready_cleared(tmp_path)
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


def test_detect_context_requires_kw_when_registry_present(tmp_path: Path):
    _write_registry(tmp_path)
    code, payload = _run(tmp_path, "ensure-frontier")
    assert code == 0, payload
    code, payload = _run(tmp_path, "detect-context")
    assert code == 1
    assert payload["ok"] is False
    assert "KW" in payload["error"]


def test_detect_context_fails_without_frontier_and_does_not_write(tmp_path: Path):
    _write_registry(tmp_path)
    _write_kw(tmp_path)
    code, payload = _run(tmp_path, "detect-context")
    assert code == 1
    assert payload["ok"] is False
    assert "frontier" in payload["error"]
    assert not (tmp_path / "lens-frontier.json").is_file()


def test_detect_context_fails_without_registry(tmp_path: Path):
    _write_kw(tmp_path)
    code, payload = _run(tmp_path, "ensure-frontier")
    assert code == 0, payload
    code, payload = _run(tmp_path, "detect-context")
    assert code == 1
    assert "section-registry" in payload["error"]


def test_detect_context_fails_when_project_root_cannot_resolve(tmp_path: Path):
    _write_registry(tmp_path)
    _write_kw(tmp_path)
    code, payload = _run(tmp_path, "ensure-frontier")
    assert code == 0, payload
    code, payload = _run(tmp_path, "detect-context", project_root=str(tmp_path))
    assert code == 1
    assert payload["ok"] is False
    assert "session" in payload["error"] or "resolve" in payload["error"]


def test_detect_context_emits_frontier_and_inert_means(tmp_path: Path):
    _write_registry(tmp_path)
    _write_kw(tmp_path)
    code, payload = _run(tmp_path, "ensure-frontier")
    assert code == 0, payload
    before = (tmp_path / "lens-frontier.json").read_text(encoding="utf-8")
    code, payload = _run(tmp_path, "detect-context")
    assert code == 0, payload
    assert payload["facts_snapshot"] == []
    assert "lens_registry" in payload
    assert payload["opens_snapshot"] == []
    assert "facts" not in payload
    assert "lenses" not in payload
    assert "opens" not in payload
    assert "frontiers" in payload
    assert payload["frontier_digest"]
    assert "I" in payload["kw_criteria"]
    assert payload["intent_baseline_refs"] == []
    assert payload["code_grounding"] is False
    assert payload["inert_means"] == ["intent", "scan"]
    assert "project_evidence_scope" not in payload
    assert (tmp_path / "lens-frontier.json").read_text(encoding="utf-8") == before


def test_add_opens_rejects_inert_intent_means(tmp_path: Path):
    _write_registry(tmp_path)
    _write_kw(tmp_path)
    raw = [
        {
            "question": "q",
            "basis": "b",
            "blocking": True,
            "lens": "I",
            "source": {"actor": "ai", "means": "intent"},
        }
    ]
    detect = json.loads(_detect_json(tmp_path, raw))
    code, payload = _run(
        tmp_path,
        "add-opens",
        "--opens-json",
        json.dumps(detect["raw_candidates"]),
        "--detect-json",
        json.dumps(detect),
    )
    assert code == 1
    assert "inert" in payload["error"]


def test_set_frontier_then_cleared_needs_fresh_detect(tmp_path: Path):
    _write_registry(tmp_path)
    _write_kw(tmp_path)
    code, payload = _run(
        tmp_path,
        "add-opens",
        "--opens-json",
        "[]",
        "--detect-json",
        _detect_json(tmp_path, []),
    )
    assert code == 0, payload
    code, payload = _run(tmp_path, "set-frontier", "--lens", "I", "--kw", "3")
    assert code == 0, payload
    code, payload = _run(tmp_path, "check-close", "--mode", "cleared")
    assert code == 1
    assert payload["ok"] is False

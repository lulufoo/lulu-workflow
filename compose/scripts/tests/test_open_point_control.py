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

from lens_frontier_schema import (  # noqa: E402
    default_lens_entry,
    lens_frontier_path,
    load_lens_frontier,
)
from open_point_store import add_opens, ensure_frontier  # noqa: E402

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
    ensure_frontier(out_dir)
    checked = ["I"]
    return json.dumps(
        {
            "checked_lenses": checked,
            "raw_candidates": raw_candidates,
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


def test_process_context_omits_digests_and_scope_without_project_root(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    code, payload = _run(tmp_path, "process-context")
    assert code == 0, payload
    assert payload["ok"] is True
    assert payload["open"]["id"] == "O-1"
    assert payload["facts_path"] == str((tmp_path / "_facts.json").resolve())
    assert "facts" not in payload
    assert "facts_digest" not in payload
    assert "open_digest" not in payload
    assert "batch_digest" not in payload
    assert "project_evidence_scope" not in payload


def test_process_context_includes_scope_when_project_root(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    root = tmp_path / "proj"
    root.mkdir()
    code, payload = _run(tmp_path, "process-context", project_root=str(root))
    assert code == 0, payload
    assert payload["project_evidence_scope"]["project_root"] == str(root.resolve())


def test_defer_open_without_digest_flags(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    code, payload = _run(
        tmp_path,
        "defer-open",
        "--open-id",
        "O-1",
        "--note",
        "later",
    )
    assert code == 0, payload
    assert payload["ok"] is True


def test_settle_resolved_is_not_a_subcommand(tmp_path: Path):
    code, payload = _run(
        tmp_path,
        "settle-resolved",
        "--open-id",
        "O-1",
        "--resolved-by",
        "F-1",
    )
    assert code != 0
    assert "settle-resolved" in payload.get("stderr", "")


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


def test_check_close_cleared_ignores_facts_mutation_after_zero_result(tmp_path: Path):
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
    (tmp_path / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "moved"}], indent=2) + "\n",
        encoding="utf-8",
    )
    code, payload = _run(
        tmp_path, "check-close", "--mode", "cleared", "--confirm"
    )
    assert code == 0, payload
    assert payload["ok"] is True


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


def test_detect_context_emits_slim_snapshots(tmp_path: Path):
    _write_registry(tmp_path)
    _write_kw(tmp_path)
    code, payload = _run(tmp_path, "ensure-frontier")
    assert code == 0, payload
    before = (tmp_path / "lens-frontier.json").read_text(encoding="utf-8")
    code, payload = _run(tmp_path, "detect-context")
    assert code == 0, payload
    assert payload["facts_snapshot"] == []
    assert payload["lens_registry"] == [
        {
            "lens": "I",
            "heading": "Intent",
            "intent": "constraints",
            "intent_boundary": "",
        }
    ]
    assert payload["opens_snapshot"] == []
    assert "facts" not in payload
    assert "lenses" not in payload
    assert "opens" not in payload
    assert "frontiers" in payload
    assert "facts_digest" not in payload
    assert "lens_digest" not in payload
    assert "opens_digest" not in payload
    assert "frontier_digest" not in payload
    assert "code_grounding" not in payload
    assert "inert_means" not in payload
    assert "I" in payload["kw_criteria"]
    assert payload["intent_baseline_refs"] == []
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


def test_set_frontier_does_not_block_cleared(tmp_path: Path):
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
    assert code == 0, payload
    assert payload["ok"] is True

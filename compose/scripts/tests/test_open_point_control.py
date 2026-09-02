#!/usr/bin/env python3
"""Tests for Open-point control CLI."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_CTL = _INDUCTIVE_DIR / "open-point" / "open_point_control.py"
sys.path.insert(0, str(_INDUCTIVE_DIR / "open-point"))
sys.path.insert(0, str(_INDUCTIVE_DIR))
for _name in ("gate", "topic", "open-point", "recompose"):
    sys.path.insert(0, str(_INDUCTIVE_DIR / "schema" / _name))

from lens_frontier_schema import (  # noqa: E402
    default_lens_entry,
    lens_frontier_path,
    load_lens_frontier,
)
from open_point_store import add_opens, ensure_frontier  # noqa: E402

_PLAN_PROFILE = (
    Path(__file__).resolve().parents[3] / "lulu-plan" / "compose-profile.json"
)
_PLAN_LENSES = ["CTX", "GO", "SC", "AR", "I", "SK", "T", "VF"]


def _bind_session(session_base: Path, profile_path: Path) -> None:
    digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    session_base.mkdir(parents=True, exist_ok=True)
    (session_base / "session-state.md").write_text(
        "---\n"
        "version: 2\n"
        "active_doc: 2\n"
        f"profile_path: {profile_path.resolve()}\n"
        f"profile_digest: {digest}\n"
        "start_id: test\n"
        "holder_finalized: true\n"
        "updated_at: 2024-01-01T00:00:00+00:00\n"
        "---\n",
        encoding="utf-8",
    )


def _slice_env(tmp_path: Path) -> tuple[Path, str]:
    _bind_session(tmp_path, _PLAN_PROFILE)
    slice_dir = tmp_path / "revision1" / "L1"
    slice_dir.mkdir(parents=True)
    return slice_dir, str(tmp_path)


def _ready_cleared(slice_dir: Path, project_root: str) -> None:
    ensure_frontier(slice_dir, project_root)


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


def _detect_json(out_dir: Path, raw_candidates, project_root: str):
    ensure_frontier(out_dir, project_root)
    path = lens_frontier_path(out_dir)
    lenses = load_lens_frontier(path)["lenses"] if path.is_file() else {}
    by_lens: dict[str, list] = {}
    for item in raw_candidates:
        if isinstance(item, dict) and item.get("lens"):
            key = str(item["lens"]).strip().upper()
            by_lens.setdefault(key, []).append(dict(item))
    verdicts = []
    for key in _PLAN_LENSES:
        entry = lenses.get(key) or default_lens_entry()
        start = int(entry.get("frontier_kw") or 0)
        hits = by_lens.get(key, [])
        verdicts.append(
            {"lens": key, "gap_kw": start if hits else None, "candidates": hits}
        )
    return json.dumps({"verdicts": verdicts})


def test_detect_context_refused_when_processing(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    add_opens(slice_dir, opens=[_human_open()], project_root=root)
    code, payload = _run(slice_dir, "detect-context", project_root=root)
    assert code == 1
    assert payload["ok"] is False
    assert "idle" in payload["error"] or "processing" in payload["error"]


def test_add_opens_json_round_trip(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    opens = [_human_open(), _human_open(question="second", blocking=False)]
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        json.dumps(opens),
        project_root=root,
    )
    assert code == 0, payload
    assert payload["ok"] is True
    registered = payload.get("opens") or payload.get("added")
    assert [item["question"] for item in registered] == [
        "What is unresolved?",
        "second",
    ]
    assert [item["id"] for item in registered] == ["O-1", "O-2"]
    code, ctx = _run(slice_dir, "resolve-context", project_root=root)
    assert code == 0, ctx
    assert ctx["state"]["phase"] == "processing"
    assert ctx["state"]["active_open_id"] == "O-1"


def test_process_context_omits_digests_and_scope_without_project_root(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    add_opens(slice_dir, opens=[_human_open()], project_root=root)
    code, payload = _run(slice_dir, "process-context")
    assert code == 0, payload
    assert payload["ok"] is True
    assert payload["open"]["id"] == "O-1"
    assert payload["facts_path"] == str((slice_dir / "_facts.json").resolve())
    assert "facts" not in payload
    assert "facts_digest" not in payload
    assert "open_digest" not in payload
    assert "batch_digest" not in payload
    assert "project_evidence_scope" not in payload


def test_process_context_includes_scope_when_project_root(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    add_opens(slice_dir, opens=[_human_open()], project_root=root)
    code, payload = _run(slice_dir, "process-context", project_root=root)
    assert code == 0, payload
    assert payload["project_evidence_scope"]["project_root"] == str(Path(root).resolve())


def test_defer_open_without_digest_flags(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    add_opens(slice_dir, opens=[_human_open()], project_root=root)
    code, payload = _run(
        slice_dir,
        "defer-open",
        "--open-id",
        "O-1",
        "--note",
        "later",
        project_root=root,
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
    slice_dir, root = _slice_env(tmp_path)
    _ready_cleared(slice_dir, root)
    add_opens(
        slice_dir,
        opens=[],
        detect=json.loads(_detect_json(slice_dir, [], root)),
        project_root=root,
    )
    code, payload = _run(slice_dir, "check-close", "--mode", "cleared", project_root=root)
    assert code == 0, payload
    assert payload["ok"] is True
    add_opens(
        slice_dir,
        opens=[
            {
                "question": "q",
                "basis": "b",
                "blocking": False,
                "source": {"actor": "human", "means": "direct"},
                "lens": "I",
            }
        ],
        project_root=root,
    )
    code, payload = _run(
        slice_dir, "check-close", "--mode", "hard-skip", project_root=root
    )
    assert code == 0, payload
    bundle_opens = json.loads(
        (slice_dir / "inductive-opens.json").read_text(encoding="utf-8")
    )
    assert any(item.get("status") == "open" for item in bundle_opens)
    state = json.loads(
        (slice_dir / "open-point-state.json").read_text(encoding="utf-8")
    )
    assert state["phase"] == "processing"


def test_check_close_cleared_ignores_facts_mutation_after_zero_result(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    _ready_cleared(slice_dir, root)
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        "[]",
        "--detect-json",
        _detect_json(slice_dir, [], root),
        project_root=root,
    )
    assert code == 0, payload
    (slice_dir / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "moved"}], indent=2) + "\n",
        encoding="utf-8",
    )
    code, payload = _run(
        slice_dir, "check-close", "--mode", "cleared", "--confirm", project_root=root
    )
    assert code == 0, payload
    assert payload["ok"] is True


def test_detect_context_fails_without_project_root(tmp_path: Path):
    slice_dir, _root = _slice_env(tmp_path)
    code, payload = _run(slice_dir, "detect-context")
    assert code == 1
    assert payload["ok"] is False
    assert "SKILL" in payload["error"]


def test_detect_context_fails_without_frontier_and_does_not_write(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    code, payload = _run(slice_dir, "detect-context", project_root=root)
    assert code == 1
    assert payload["ok"] is False
    assert "frontier" in payload["error"]
    assert not (slice_dir / "lens-frontier.json").is_file()


def test_detect_context_fails_when_skill_cannot_resolve(tmp_path: Path):
    (tmp_path / "section-registry.json").write_text("{}", encoding="utf-8")
    code, payload = _run(tmp_path, "detect-context", project_root=str(tmp_path))
    assert code == 1
    assert payload["ok"] is False
    assert "SKILL" in payload["error"]


def test_detect_context_emits_slim_snapshots(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    code, payload = _run(slice_dir, "ensure-frontier", project_root=root)
    assert code == 0, payload
    before = (slice_dir / "lens-frontier.json").read_text(encoding="utf-8")
    code, payload = _run(slice_dir, "detect-context", project_root=root)
    assert code == 0, payload
    assert "facts_snapshot" not in payload
    assert "lens_registry" not in payload
    assert "kw_criteria" not in payload
    assert payload["opens_snapshot"] == []
    assert "facts" not in payload
    assert "lenses" not in payload
    assert "opens" not in payload
    assert "frontiers" in payload
    assert list(payload["frontiers"]["lenses"]) == _PLAN_LENSES
    assert "facts_digest" not in payload
    assert "lens_digest" not in payload
    assert "opens_digest" not in payload
    assert "frontier_digest" not in payload
    assert "code_grounding" not in payload
    assert "inert_means" not in payload
    assert payload["intent_baseline_refs"] == []
    assert payload["project_evidence_scope"]["project_root"] == str(Path(root).resolve())
    assert (slice_dir / "lens-frontier.json").read_text(encoding="utf-8") == before
    assert not (slice_dir / "section-registry.json").exists()
    assert not (slice_dir / "section-kw-criteria.md").exists()


def test_add_opens_rejects_inert_intent_means(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    raw = [
        {
            "question": "q",
            "basis": "b",
            "blocking": True,
            "lens": "I",
            "source": {"actor": "ai", "means": "intent"},
        }
    ]
    detect = json.loads(_detect_json(slice_dir, raw, root))
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        json.dumps(raw),
        "--detect-json",
        json.dumps(detect),
        project_root=root,
    )
    assert code == 1
    assert "inert" in payload["error"]


def test_set_frontier_does_not_block_cleared(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        "[]",
        "--detect-json",
        _detect_json(slice_dir, [], root),
        project_root=root,
    )
    assert code == 0, payload
    code, payload = _run(
        slice_dir, "set-frontier", "--lens", "I", "--kw", "3", project_root=root
    )
    assert code == 0, payload
    code, payload = _run(slice_dir, "check-close", "--mode", "cleared", project_root=root)
    assert code == 0, payload
    assert payload["ok"] is True


def test_detect_context_fetches_registry_from_skill_without_slice_file(
    tmp_path: Path,
):
    slice_dir, root = _slice_env(tmp_path)
    code, payload = _run(slice_dir, "ensure-frontier", project_root=root)
    assert code == 0, payload
    code, payload = _run(slice_dir, "detect-context", project_root=root)
    assert code == 0, payload
    assert "lens_registry" not in payload
    assert list(payload["frontiers"]["lenses"]) == _PLAN_LENSES
    assert not (slice_dir / "section-registry.json").exists()
    assert not (slice_dir / "section-kw-criteria.md").exists()


def test_detect_lens_context_filters_facts_and_rejects_unknown(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    code, payload = _run(slice_dir, "ensure-frontier", project_root=root)
    assert code == 0, payload
    (slice_dir / "_facts.json").write_text(
        json.dumps(
            [
                {
                    "id": "F-ctx",
                    "text": "ctx",
                    "lens_tags": ["CTX"],
                    "origin": {"type": "seed"},
                },
                {"id": "F-empty", "text": "none", "lens_tags": []},
                {"id": "F-go", "text": "go", "lens_tags": ["GO"]},
            ]
        ),
        encoding="utf-8",
    )
    code, payload = _run(
        slice_dir, "detect-lens-context", "--lens", "CTX", project_root=root
    )
    assert code == 0, payload
    assert payload["lens_registry"]["lens"] == "CTX"
    assert payload["lens_registry"]["heading"] == "Context"
    assert isinstance(payload["kw_criteria"], str)
    assert "KW0" in payload["kw_criteria"]
    assert [item["id"] for item in payload["facts_snapshot"]] == ["F-ctx"]
    assert payload["facts_snapshot"][0]["origin"] == {"type": "seed"}
    assert "opens_snapshot" not in payload
    assert "frontiers" not in payload
    assert not (slice_dir / "section-registry.json").exists()
    code, payload = _run(
        slice_dir, "detect-lens-context", "--lens", "NOPE", project_root=root
    )
    assert code == 1
    assert "unknown lens" in payload["error"]


def test_detect_lens_context_refused_when_processing(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    add_opens(slice_dir, opens=[_human_open()], project_root=root)
    code, payload = _run(
        slice_dir, "detect-lens-context", "--lens", "I", project_root=root
    )
    assert code == 1
    assert payload["ok"] is False
    assert "idle" in payload["error"] or "processing" in payload["error"]

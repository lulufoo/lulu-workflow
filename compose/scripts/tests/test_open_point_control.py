#!/usr/bin/env python3
"""Tests for Open-point control CLI."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_CTL = _INDUCTIVE_DIR / "open-point" / "open_point_control.py"
sys.path.insert(0, str(_INDUCTIVE_DIR / "open-point"))
sys.path.insert(0, str(_INDUCTIVE_DIR))
for _name in ("gate", "topic", "open-point"):
    sys.path.insert(0, str(_INDUCTIVE_DIR / "schema" / _name))

from inductive_gate_state_schema import (  # noqa: E402
    init_gate_state,
    save_gate_state,
)
from lens_frontier_schema import (  # noqa: E402
    default_lens_entry,
    lens_frontier_path,
    load_lens_frontier,
)
from open_point_store import add_opens, ensure_frontier  # noqa: E402

_PLAN_PROFILE = (
    Path(__file__).resolve().parents[3] / "lulu-plan" / "compose-profile.json"
)
_PLAN_DOMAIN = (
    Path(__file__).resolve().parents[3] / "lulu-plan" / "templates" / "domain-instance.json"
)
_PLAN_LENSES = ["CTX", "GO", "SC", "AR", "I", "SK", "T", "VF"]
_DERIVED_LENSES = ["SK", "T"]
_ASKED_LENSES = [lens for lens in _PLAN_LENSES if lens not in _DERIVED_LENSES]


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


def _write_gate_state(slice_dir: Path, *, stage: str = "lulu-plan") -> None:
    save_gate_state(
        slice_dir / "inductive-gate-state.json",
        init_gate_state(cycle_id="c1", stage=stage),
    )


def _slice_env(tmp_path: Path) -> tuple[Path, str]:
    _bind_session(tmp_path, _PLAN_PROFILE)
    slice_dir = tmp_path / "revision1" / "execution"
    slice_dir.mkdir(parents=True)
    _write_gate_state(slice_dir)
    return slice_dir, str(tmp_path)


def _plan_guide() -> dict[str, str]:
    domain = json.loads(_PLAN_DOMAIN.read_text(encoding="utf-8"))
    return {
        "cognitive_frame": domain["cognitive_frame"],
        "intent_anchor": domain["intent_anchor"],
    }


def _ready_cleared(slice_dir: Path, project_root: str) -> None:
    ensure_frontier(slice_dir, project_root)


def _run(
    out_dir: Path,
    *args: str,
    project_root: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, dict]:
    cmd = [sys.executable, str(_CTL), "--out-dir", str(out_dir)]
    if project_root is not None:
        cmd.extend(["--project-root", project_root])
    cmd.extend(args)
    env = None
    if extra_env:
        env = {**os.environ, **extra_env}
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
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
    for key in _ASKED_LENSES:
        entry = lenses.get(key) or default_lens_entry()
        start = int(entry.get("frontier_kw") or 0)
        hits = by_lens.get(key, [])
        verdicts.append(
            {"lens": key, "gap_kw": start if hits else None, "candidates": hits}
        )
    return json.dumps({"verdicts": verdicts})


def _opens_json(opens: list) -> str:
    return json.dumps({"opens": opens})


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
        _opens_json(opens),
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
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        json.dumps(opens),
        project_root=root,
    )
    assert code == 1
    assert payload["ok"] is False
    assert 'JSON object {"opens": [...]}' in payload["error"]
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


def test_process_context_returns_group_and_skip_open_accepts_group(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    add_opens(
        slice_dir,
        opens=[_human_open(), _human_open(question="second", blocking=False)],
        project_root=root,
    )
    code, payload = _run(slice_dir, "process-context")
    assert code == 0, payload
    assert [item["id"] for item in payload["group"]["opens"]] == ["O-1", "O-2"]
    assert payload["group"]["lens"] == payload["open"]["lens"]
    code, payload = _run(slice_dir, "skip-open", "--open-id", "O-1", "--open-id", "O-2")
    assert code == 0, payload
    assert payload["state"]["active_open_id"] == "O-1"
    assert payload["batch"]["open_ids"] == ["O-1", "O-2"]


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
        _opens_json([]),
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
    assert "frontiers" not in payload
    assert payload["pending_lenses"] == _ASKED_LENSES
    assert payload["guide"] == _plan_guide()
    assert set(payload["guide"]) == {"cognitive_frame", "intent_anchor"}
    assert "frontier_kw" not in json.dumps(payload)
    assert "facts_digest" not in payload
    assert "lens_digest" not in payload
    assert "opens_digest" not in payload
    assert "frontier_digest" not in payload
    assert "code_grounding" not in payload
    assert "inert_means" not in payload
    assert "intent_baseline_refs" not in payload
    assert "project_evidence_scope" not in payload
    assert (slice_dir / "lens-frontier.json").read_text(encoding="utf-8") == before
    assert not (slice_dir / "section-registry.json").exists()
    assert not (slice_dir / "section-kw-criteria.md").exists()


def test_detect_context_fails_without_gate_state(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    (slice_dir / "inductive-gate-state.json").unlink()
    code, payload = _run(slice_dir, "ensure-frontier", project_root=root)
    assert code == 0, payload
    code, payload = _run(slice_dir, "detect-context", project_root=root)
    assert code == 1
    assert payload["ok"] is False
    assert "gate state" in payload["error"]


def test_detect_context_fails_when_stage_empty(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    _write_gate_state(slice_dir, stage="")
    code, payload = _run(slice_dir, "ensure-frontier", project_root=root)
    assert code == 0, payload
    code, payload = _run(slice_dir, "detect-context", project_root=root)
    assert code == 1
    assert payload["ok"] is False
    assert "stage" in payload["error"].lower()


def test_detect_context_fails_when_domain_unresolved(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    _write_gate_state(slice_dir, stage="not-a-compose-profile")
    code, payload = _run(slice_dir, "ensure-frontier", project_root=root)
    assert code == 0, payload
    code, payload = _run(slice_dir, "detect-context", project_root=root)
    assert code == 1
    assert payload["ok"] is False
    error = payload["error"].lower()
    assert "guide" in error or "profile" in error or "domain" in error


def test_add_opens_rejects_non_probe_detect_means(tmp_path: Path):
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
        _opens_json(raw),
        "--detect-json",
        json.dumps(detect),
        project_root=root,
    )
    assert code == 1
    assert "must be probe" in payload["error"]
    assert "inert" not in payload["error"]


def test_set_frontier_does_not_block_cleared(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        _opens_json([]),
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
    assert payload["pending_lenses"] == _ASKED_LENSES
    assert not (slice_dir / "section-registry.json").exists()
    assert not (slice_dir / "section-kw-criteria.md").exists()


def _skip_clean_env(tmp_path: Path) -> dict[str, str]:
    path = tmp_path / "compose-config.json"
    path.write_text(json.dumps({"detect_skip_clean": True}), encoding="utf-8")
    return {"LULU_COMPOSE_CONFIG": str(path)}


def _write_facts(slice_dir: Path, ctx_text: str) -> None:
    (slice_dir / "_facts.json").write_text(
        json.dumps([{"id": "F-ctx", "text": ctx_text, "lens": "CTX"}]),
        encoding="utf-8",
    )


def _switch_off_env(tmp_path: Path) -> dict[str, str]:
    path = tmp_path / "compose-config-off.json"
    path.write_text(json.dumps({"detect_skip_clean": False}), encoding="utf-8")
    return {"LULU_COMPOSE_CONFIG": str(path)}


def test_empty_detect_records_clean_but_switch_off_keeps_all_pending(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    off_env = _switch_off_env(tmp_path)
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        _opens_json([]),
        "--detect-json",
        _detect_json(slice_dir, [], root),
        project_root=root,
        extra_env=off_env,
    )
    assert code == 0, payload
    frontier = load_lens_frontier(lens_frontier_path(slice_dir))
    for lens in _ASKED_LENSES:
        assert frontier["lenses"][lens].get("clean")
    for lens in _DERIVED_LENSES:
        assert not frontier["lenses"][lens].get("clean")
    code, payload = _run(
        slice_dir, "detect-context", project_root=root, extra_env=off_env
    )
    assert code == 0, payload
    assert payload["pending_lenses"] == _ASKED_LENSES
    assert "clean" not in json.dumps(payload["pending_lenses"])


def test_switch_on_skips_clean_lenses_until_facts_change(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    skip_env = _skip_clean_env(tmp_path)
    _write_facts(slice_dir, "ctx v1")
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        _opens_json([]),
        "--detect-json",
        _detect_json(slice_dir, [], root),
        project_root=root,
        extra_env=skip_env,
    )
    assert code == 0, payload
    code, payload = _run(
        slice_dir, "detect-context", project_root=root, extra_env=skip_env
    )
    assert code == 0, payload
    assert payload["pending_lenses"] == []
    _write_facts(slice_dir, "ctx v2")
    code, payload = _run(
        slice_dir, "detect-context", project_root=root, extra_env=skip_env
    )
    assert code == 0, payload
    assert payload["pending_lenses"] == ["CTX"]


def test_switch_on_add_opens_fills_carried_lenses_and_rejects_extra(tmp_path: Path):
    slice_dir, root = _slice_env(tmp_path)
    skip_env = _skip_clean_env(tmp_path)
    _write_facts(slice_dir, "ctx v1")
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        _opens_json([]),
        "--detect-json",
        _detect_json(slice_dir, [], root),
        project_root=root,
        extra_env=skip_env,
    )
    assert code == 0, payload
    _write_facts(slice_dir, "ctx v2")
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        _opens_json([]),
        "--detect-json",
        _detect_json(slice_dir, [], root),
        project_root=root,
        extra_env=skip_env,
    )
    assert code == 1
    assert "unknown lenses" in payload["error"]
    raw = [
        {
            "question": "q",
            "basis": "b",
            "blocking": True,
            "lens": "CTX",
            "source": {"actor": "ai", "means": "probe"},
        }
    ]
    verdicts = {"verdicts": [{"lens": "CTX", "gap_kw": 1, "candidates": raw}]}
    code, payload = _run(
        slice_dir,
        "add-opens",
        "--opens-json",
        _opens_json(raw),
        "--detect-json",
        json.dumps(verdicts),
        project_root=root,
        extra_env=skip_env,
    )
    assert code == 0, payload
    receipt = payload["receipt"]
    assert [item["lens"] for item in receipt["lens_measurements"]] == _PLAN_LENSES
    by_lens = {item["lens"]: item["gap_kw"] for item in receipt["lens_measurements"]}
    assert by_lens["CTX"] == 1
    assert all(by_lens[lens] is None for lens in _PLAN_LENSES if lens != "CTX")
    frontier = load_lens_frontier(lens_frontier_path(slice_dir))
    assert frontier["lenses"]["CTX"]["frontier_kw"] == 1
    assert "clean" not in frontier["lenses"]["CTX"]
    assert frontier["lenses"]["GO"].get("clean")


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
                    "lens": "CTX",
                    "origin": {"type": "seed"},
                },
                {"id": "F-empty", "text": "none"},
                {"id": "F-go", "text": "go", "lens": "GO"},
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
    assert "frontier_kw" not in payload
    assert isinstance(payload["kw_criteria"], str)
    assert "KW0" not in payload["kw_criteria"]
    assert "KW1" in payload["kw_criteria"]
    assert payload["facts_snapshot"] == [{"id": "F-ctx", "text": "ctx"}]
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

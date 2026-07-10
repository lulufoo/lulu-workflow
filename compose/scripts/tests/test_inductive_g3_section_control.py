#!/usr/bin/env python3
"""Tests for the inductive Gate 3 frontier-sweep machine.

Covers the frontier_kw state plus the set-frontier / seed-decision /
clear-section subcommands that replaced the one-shot commit-section.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SECTION_CTL = _INDUCTIVE_DIR / "inductive_g3_section_control.py"

sys.path.insert(0, str(_INDUCTIVE_DIR))
from g3_section_pointer_schema import (  # noqa: E402
    FRONTIER_TARGET_DEFAULT,
    init_section_pointer,
    normalize_section_pointer,
    set_frontier,
    validate_section_pointer,
)


def _run(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_SECTION_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


def _seed(out_dir: Path, active: str = "I") -> None:
    code, payload = _run(out_dir, "init-pointer", "--sections", "I,ST", "--mandatory", "")
    assert code == 0, payload
    code, payload = _run(out_dir, "activate-section", "--section", active)
    assert code == 0, payload


def _blocking_ep_json(section: str) -> str:
    return json.dumps(
        {
            "section": section,
            "block": "blk",
            "method": "impl_gap",
            "kw": "KW1",
            "type": "undecided",
            "description": "a blocking gap",
            "code_refs": [],
            "confidence": "direct",
            "blocking": True,
            "source": "ai_scan",
            "status": "open",
        }
    )


# --- schema layer -----------------------------------------------------------

def test_default_frontier_is_zero():
    ptr = init_section_pointer(coverage_sections=["I", "ST"], mandatory=[], cycle_id="c1")
    assert ptr["sections"]["I"]["frontier_kw"] == 0
    assert validate_section_pointer(ptr) == []


def test_set_frontier_sets_value():
    ptr = init_section_pointer(coverage_sections=["I"], mandatory=[], cycle_id="c1")
    ptr = set_frontier(ptr, "I", 2)
    assert ptr["sections"]["I"]["frontier_kw"] == 2


def test_set_frontier_rejects_out_of_range():
    ptr = init_section_pointer(coverage_sections=["I"], mandatory=[], cycle_id="c1")
    for bad in (-1, 5):
        try:
            set_frontier(ptr, "I", bad)
        except ValueError:
            continue
        raise AssertionError(f"frontier_kw={bad} should have been rejected")


def test_normalize_clamps_frontier():
    raw = {
        "version": "1",
        "coverage_order": ["I"],
        "sections": {"I": {"status": "active", "frontier_kw": 99}},
        "mandatory": [],
        "active_section": "I",
    }
    norm = normalize_section_pointer(raw)
    assert norm["sections"]["I"]["frontier_kw"] == 4


# --- control layer (CLI) ----------------------------------------------------

def test_set_frontier_focus_guard(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(tmp_path, "set-frontier", "--section", "ST", "--kw", "1")
    assert code == 1 and not payload["ok"]
    assert "focus guard" in payload["error"]


def test_status_reports_frontier(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", "2")
    code, payload = _run(tmp_path, "status")
    assert code == 0
    assert payload["frontier"] == {"I": 2, "ST": 0}


def test_seed_decision_accumulates_decisions(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "first")
    _run(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "second")
    code, payload = _run(tmp_path, "get-section", "--section", "I")
    assert code == 0
    texts = [d["text"] for d in payload["section"]["decisions"]]
    assert texts == ["first", "second"]


def test_clear_blocked_by_low_frontier(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "body")
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 1 and "frontier_kw" in payload["error"]


def test_clear_blocked_by_empty_bucket(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 1 and "no decisions" in payload["error"]


def test_clear_blocked_by_blocking_open(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "set-frontier", "--section", "ST", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "ST", "--kw", "1", "--text", "body")
    _run(
        tmp_path,
        "add-open",
        "--section",
        "ST",
        "--kw",
        "2",
        "--trigger",
        "ai",
        "--means",
        "ai_scan",
        "--problem",
        "a blocking gap",
        "--blocking",
        "true",
    )
    code, payload = _run(tmp_path, "clear-section", "--section", "ST")
    assert code == 1 and "blocking open" in payload["error"]


def test_clear_succeeds_when_ready(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "the I figure")
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 0 and payload["cleared"] == "I"
    code, status = _run(tmp_path, "status")
    assert status["sections"]["I"] == "cleared"


def test_update_open_patches_fields(tmp_path):
    _seed(tmp_path, active="ST")
    code, payload = _run(
        tmp_path,
        "add-open",
        "--section",
        "ST",
        "--kw",
        "2",
        "--trigger",
        "ai",
        "--means",
        "ai_scan",
        "--problem",
        "gap",
        "--leaning",
        "old",
    )
    assert code == 0
    oid = payload["id"]
    code, payload = _run(
        tmp_path,
        "update-open",
        "--section",
        "ST",
        "--open-id",
        oid,
        "--leaning",
        "new leaning",
        "--provenance-note",
        "also from intent_baseline",
        "--blocking",
        "false",
    )
    assert code == 0, payload
    assert payload["open"]["leaning"].startswith("new leaning")
    assert "also from intent_baseline" in payload["open"]["leaning"]
    assert payload["open"]["blocking"] is False


def test_deprecated_append_to_section_fails(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(
        tmp_path, "append-to-section", "--section", "I", "--content", "x"
    )
    assert code == 1
    assert "REMOVED" in payload["error"] or "removed" in payload["error"]


def test_init_pointer_does_not_create_ep_ledger(tmp_path):
    code, payload = _run(tmp_path, "init-pointer", "--sections", "I,ST", "--mandatory", "")
    assert code == 0, payload
    assert not (tmp_path / "exposed-points.json").exists()
    assert (tmp_path / "inductive-scope" / "_index.json").exists()


# --- section-SoT command surface (A2) ---------------------------------------

def test_seed_decision_appends_with_seed_scope_provenance(tmp_path):
    _seed(tmp_path, active="ST")
    code, payload = _run(
        tmp_path,
        "seed-decision",
        "--section",
        "ST",
        "--kw",
        "1",
        "--text",
        "限流器置于 API 网关层",
    )
    assert code == 0, payload
    assert payload["id"] == "ST-d1"
    sec = json.loads(
        (tmp_path / "inductive-scope" / "ST.json").read_text(encoding="utf-8")
    )
    assert sec["decisions"][0]["trigger"] == "seed"
    assert sec["decisions"][0]["means"] == "scope"
    assert sec["decisions"][0]["confidence"] == "direct"
    assert sec["decisions"][0]["text"] == "限流器置于 API 网关层"
    assert sec["decisions"][0]["code_refs"] == []


def test_add_open_requires_trigger_and_means(tmp_path):
    _seed(tmp_path, active="ST")
    code, payload = _run(
        tmp_path,
        "add-open",
        "--section",
        "ST",
        "--kw",
        "2",
        "--problem",
        "状态是否共享？",
    )
    assert code == 1
    assert not payload.get("ok", True)
    assert "trigger" in payload.get("error", "").lower() or "means" in payload.get(
        "error", ""
    ).lower()


def test_add_open_and_get_section(tmp_path):
    _seed(tmp_path, active="ST")
    code, payload = _run(
        tmp_path,
        "add-open",
        "--section",
        "ST",
        "--kw",
        "2",
        "--trigger",
        "ai",
        "--means",
        "probe",
        "--problem",
        "网关多实例时限流状态是否共享？",
        "--leaning",
        "分布式令牌桶",
        "--blocking",
        "true",
    )
    assert code == 0, payload
    assert payload["id"] == "ST-o1"
    code, got = _run(tmp_path, "get-section", "--section", "ST")
    assert code == 0, got
    assert got["section"]["open"][0]["trigger"] == "ai"
    assert got["section"]["open"][0]["means"] == "probe"
    assert got["section"]["open"][0]["blocking"] is True


# --- section-SoT command surface (A3) ---------------------------------------

def test_settle_open_moves_to_decisions_and_inherits_trigger_means(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "add-open",
        "--section",
        "ST",
        "--kw",
        "2",
        "--trigger",
        "ai",
        "--means",
        "probe",
        "--problem",
        "共享？",
        "--leaning",
        "Redis",
        "--intent-ref",
        "SPEC-1",
        "--blocking",
        "true",
    )
    code, payload = _run(
        tmp_path,
        "settle-open",
        "--section",
        "ST",
        "--open-id",
        "ST-o1",
        "--text",
        "用 Redis 令牌桶共享状态",
        "--rationale",
        "多实例必须共享计数",
        "--confidence",
        "direct",
    )
    assert code == 0, payload
    assert payload["decision_id"] == "ST-d1"
    code, got = _run(tmp_path, "get-section", "--section", "ST")
    sec = got["section"]
    assert sec["open"] == []
    d = sec["decisions"][0]
    assert d["text"] == "用 Redis 令牌桶共享状态"
    assert d["trigger"] == "ai"
    assert d["means"] == "probe"
    assert d["intent_ref"] == "SPEC-1"
    assert d["rationale"] == "多实例必须共享计数"
    assert d["confidence"] == "direct"


def test_defer_open_moves_to_deferred(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "add-open",
        "--section",
        "ST",
        "--kw",
        "3",
        "--trigger",
        "human",
        "--means",
        "direct",
        "--problem",
        "HA later",
        "--blocking",
        "false",
    )
    code, payload = _run(
        tmp_path,
        "defer-open",
        "--section",
        "ST",
        "--open-id",
        "ST-o1",
        "--note",
        "本轮不展开",
    )
    assert code == 0, payload
    code, got = _run(tmp_path, "get-section", "--section", "ST")
    sec = got["section"]
    assert sec["open"] == []
    assert sec["deferred"][0]["id"] == "ST-o1"
    assert sec["deferred"][0]["note"] == "本轮不展开"


def test_update_decision_and_attach_code_refs(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "seed-decision",
        "--section",
        "ST",
        "--kw",
        "1",
        "--text",
        "初稿",
    )
    code, payload = _run(
        tmp_path,
        "update-decision",
        "--section",
        "ST",
        "--decision-id",
        "ST-d1",
        "--text",
        "修订稿",
        "--rationale",
        "更准",
    )
    assert code == 0, payload
    code, payload = _run(
        tmp_path,
        "attach-code-refs",
        "--section",
        "ST",
        "--id",
        "ST-d1",
        "--refs",
        "gateway/router.go::HTTPIngress (L88)",
    )
    assert code == 0, payload
    code, got = _run(tmp_path, "get-section", "--section", "ST")
    d = got["section"]["decisions"][0]
    assert d["text"] == "修订稿"
    assert d["rationale"] == "更准"
    assert d["code_refs"] == ["gateway/router.go::HTTPIngress (L88)"]


# --- section-SoT view (B1) --------------------------------------------------

def test_view_synthesis_off_assembles_decisions_text_only(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "seed-decision", "--section", "ST", "--kw", "1", "--text", "A-decision")
    _run(tmp_path, "activate-section", "--section", "I")
    _run(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "B-decision")
    _run(
        tmp_path,
        "add-open",
        "--section",
        "I",
        "--kw",
        "2",
        "--trigger",
        "ai",
        "--means",
        "ai_scan",
        "--problem",
        "should-not-appear-in-off",
        "--blocking",
        "false",
    )
    code, payload = _run(
        tmp_path, "view", "--synthesis", "off", "--scope", "all"
    )
    assert code == 0, payload
    md = payload["markdown"]
    assert "A-decision" in md and "B-decision" in md
    assert "should-not-appear-in-off" not in md
    assert "## ST" in md or "# ST" in md


def test_view_synthesis_on_returns_context_bundle_json(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "seed-decision", "--section", "ST", "--kw", "1", "--text", "A")
    code, payload = _run(
        tmp_path,
        "view",
        "--synthesis",
        "on",
        "--scope",
        "ST",
        "--granularity",
        "架构大局",
    )
    assert code == 0, payload
    assert "index" in payload["bundle"]
    assert "sections" in payload["bundle"]
    assert payload["granularity"] == "架构大局"
    assert payload["bundle"]["sections"][0]["key"] == "ST"
    assert "decisions" in payload["bundle"]["sections"][0]
    assert "open" in payload["bundle"]["sections"][0]


# --- section-SoT recompose / checkpoint (C1) --------------------------------

def test_checkpoint_sets_last_checkpoint(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(tmp_path, "checkpoint", "--name", "shape")
    assert code == 0, payload
    assert payload["last_checkpoint"] == "shape"
    idx = json.loads(
        (tmp_path / "inductive-scope" / "_index.json").read_text(encoding="utf-8")
    )
    assert idx["last_checkpoint"] == "shape"


def test_recompose_check_requires_shape_checkpoint(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "body")
    _run(tmp_path, "clear-section", "--section", "I")
    code, payload = _run(tmp_path, "recompose-check")
    assert code == 1
    assert payload.get("ok") is False
    errors = payload.get("recompose_check", {}).get("errors", [])
    assert any("shape checkpoint" in e for e in errors)


def test_recompose_check_passes_with_shape_checkpoint(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "body")
    _run(tmp_path, "clear-section", "--section", "I")
    code, ck = _run(tmp_path, "checkpoint", "--name", "shape")
    assert code == 0, ck
    code, payload = _run(tmp_path, "recompose-check")
    assert code == 0, payload
    rc = payload["recompose_check"]
    assert rc["reforms_shape"] is True
    assert rc["shape_absorbed"] is True
    assert rc["errors"] == []
    # git sha best-effort (present when cwd is a git repo)
    assert "checkpoint_git_sha" in rc

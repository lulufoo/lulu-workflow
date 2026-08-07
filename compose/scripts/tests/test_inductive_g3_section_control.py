#!/usr/bin/env python3
"""Tests for K4 fact-native Gate 3 control (triple store)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def _write_facts_file(path: Path, entries: list[dict]) -> Path:
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


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


def test_seed_decision_writes_facts(tmp_path):
    _seed(tmp_path, active="I")
    code, p1 = _run(
        tmp_path,
        "seed-decision",
        "--section", "I",
        "--lens-tags", "I",
        "--text", "first",
    )
    assert code == 0, p1
    assert p1["id"] == "F-1"
    code, p2 = _run(
        tmp_path,
        "seed-decision",
        "--section", "I",
        "--lens-tags", "I",
        "--text", "second",
    )
    assert code == 0, p2
    assert p2["id"] == "F-2"
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert [f["text"] for f in facts] == ["first", "second"]
    assert facts[0]["origin"]["type"] == "seed"
    assert facts[0]["lens_tags"] == ["I"]
    # Maturity file has no decisions
    sec = json.loads((tmp_path / "inductive-scope" / "I.json").read_text(encoding="utf-8"))
    assert "decisions" not in sec
    assert sec["status"] == "active"


def test_add_open_writes_opens_without_focus_guard(tmp_path):
    _seed(tmp_path, active="I")
    # No --section; no focus guard — can add open while focus is I
    code, payload = _run(
        tmp_path,
        "add-open",
        "--kw", "2",
        "--trigger", "ai",
        "--means", "ai_scan",
        "--problem", "a gap",
        "--detected-under", "ST",
        "--blocking", "true",
    )
    assert code == 0, payload
    assert payload["id"] == "O-1"
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["id"] == "O-1"
    assert opens[0]["status"] == "open"
    assert opens[0]["detected_under"] == "ST"
    assert opens[0]["source"] == {"trigger": "ai", "means": "ai_scan"}


def test_settle_open_one_to_n_facts(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "add-open",
        "--kw", "2",
        "--trigger", "ai",
        "--means", "ai_probe",
        "--problem", "共享？",
        "--blocking", "true",
    )
    ff = _write_facts_file(
        tmp_path / "settle.json",
        [
            {"text": "fact A", "lens_tags": ["ST", "I"]},
            {"text": "fact B", "lens_tags": ["ST"]},
        ],
    )
    code, payload = _run(
        tmp_path,
        "settle-open",
        "--open-id", "O-1",
        "--facts-file", str(ff),
    )
    assert code != 0  # archive-10.0: --confirm required

    code, payload = _run(
        tmp_path,
        "settle-open",
        "--open-id", "O-1",
        "--facts-file", str(ff),
        "--confirm",
    )
    assert code == 0, payload
    assert payload["fact_ids"] == ["F-1", "F-2"]
    assert payload.get("stale_signal") is True
    assert payload.get("suggest_check") is True
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert facts[0]["origin"] == {"type": "discovered", "ref": ["O-1"]}
    assert facts[0]["lens_tags"] == ["ST", "I"]
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "settled"
    assert opens[0]["resolved_by"] == ["F-1", "F-2"]


def test_seed_decision_declares_anchors(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(
        tmp_path,
        "seed-decision",
        "--section", "I",
        "--lens-tags", "I",
        "--text", "seed with anchor",
        "--anchors", json.dumps([{"kind": "path", "value": "a/b/"}]),
    )
    assert code == 0, payload
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert facts[0]["anchors"] == [{"kind": "path", "value": "a/b/"}]


def test_seed_decision_rejects_bad_anchors_json(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(
        tmp_path,
        "seed-decision",
        "--section", "I",
        "--lens-tags", "I",
        "--text", "x",
        "--anchors", "{not json",
    )
    assert code == 1 and not payload["ok"]
    assert "--anchors must be a JSON array" in payload["error"]


def test_settle_open_uses_declared_entry_anchors(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "add-open",
        "--kw", "2", "--trigger", "ai", "--means", "ai_probe",
        "--problem", "q", "--blocking", "true",
    )
    ff = _write_facts_file(
        tmp_path / "settle.json",
        [
            {
                "text": "declared fact",
                "lens_tags": ["ST"],
                "anchors": [{"kind": "artifact", "value": "attachments.json"}],
            },
        ],
    )
    code, payload = _run(
        tmp_path,
        "settle-open",
        "--open-id",
        "O-1",
        "--facts-file",
        str(ff),
        "--confirm",
    )
    assert code == 0, payload
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert facts[0]["anchors"] == [{"kind": "artifact", "value": "attachments.json"}]


def test_settle_open_fallback_distributes_code_refs(tmp_path):
    """Undeclared entry: an open code_ref whose symbol/path appears in the fact
    text is projected as a code_ref anchor (line-number parens stripped)."""
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "add-open",
        "--kw", "2", "--trigger", "ai", "--means", "ai_probe",
        "--problem", "q", "--blocking", "true",
    )
    _run(
        tmp_path,
        "attach-code-refs",
        "--id", "O-1",
        "--refs", "paths.rs::plan_tasks_task_dir (72),other.rs::unused_symbol (9)",
    )
    ff = _write_facts_file(
        tmp_path / "settle.json",
        [
            {"text": "uses plan_tasks_task_dir to resolve dir", "lens_tags": ["ST"]},
        ],
    )
    code, payload = _run(
        tmp_path,
        "settle-open",
        "--open-id",
        "O-1",
        "--facts-file",
        str(ff),
        "--confirm",
    )
    assert code == 0, payload
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    # matched ref projected (parens stripped); unmatched ref stays on open only
    assert facts[0]["anchors"] == [
        {"kind": "code_ref", "value": "paths.rs::plan_tasks_task_dir"},
    ]
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert "other.rs::unused_symbol (9)" in opens[0]["code_refs"]


def test_reject_open(tmp_path):
    _seed(tmp_path, active="I")
    _run(
        tmp_path,
        "add-open",
        "--kw", "1",
        "--trigger", "human",
        "--means", "human_direct",
        "--problem", "out of domain",
        "--blocking", "true",
    )
    code, payload = _run(
        tmp_path,
        "reject-open",
        "--open-id", "O-1",
        "--reason", "真·域外",
    )
    assert code == 0, payload
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "rejected"
    assert opens[0]["reason"] == "真·域外"


def test_clear_blocked_by_low_frontier(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "body")
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 1 and "frontier_kw" in payload["error"]


def test_clear_blocked_by_empty_facts(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 1 and "no facts" in payload["error"]


def test_clear_blocked_by_blocking_open(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "set-frontier", "--section", "ST", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "body")
    _run(
        tmp_path,
        "add-open",
        "--kw", "2",
        "--trigger", "ai",
        "--means", "ai_scan",
        "--problem", "a blocking gap",
        "--blocking", "true",
        "--detected-under", "ST",
    )
    code, payload = _run(tmp_path, "clear-section", "--section", "ST")
    assert code == 1 and "blocking open" in payload["error"]


def test_clear_ignores_blocking_open_on_other_lens(tmp_path):
    """clear-section is per-lens; foreign/null-home blockers belong to Exit."""
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "body")
    _run(
        tmp_path,
        "add-open",
        "--kw", "2",
        "--trigger", "ai",
        "--means", "ai_scan",
        "--problem", "ST gap",
        "--blocking", "true",
        "--detected-under", "ST",
    )
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 0, payload
    assert payload["cleared"] == "I"


def test_clear_succeeds_when_ready(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "the I figure")
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 0 and payload["cleared"] == "I"
    code, status = _run(tmp_path, "status")
    assert status["sections"]["I"] == "cleared"


def test_check_coverage_blocking_from_opens(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "I body")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "clear-section", "--section", "I")
    _run(tmp_path, "activate-section", "--section", "ST")
    _run(tmp_path, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "ST body")
    _run(tmp_path, "set-frontier", "--section", "ST", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "clear-section", "--section", "ST")
    # Both cleared — coverage ok until we add a blocking open
    code, payload = _run(tmp_path, "check-coverage")
    assert code == 0, payload
    _run(
        tmp_path,
        "add-open",
        "--kw", "1",
        "--trigger", "human",
        "--means", "human_direct",
        "--problem", "late blocker",
        "--blocking", "true",
    )
    code, payload = _run(tmp_path, "check-coverage")
    assert code == 1
    assert payload.get("ok") is False
    assert any("blocking" in e for e in payload.get("errors", []))


def test_recompose_facts_without_maturity(tmp_path):
    """Lens present in facts but pointer still untouched → recompose error."""
    _seed(tmp_path, active="I")
    # Seed a fact tagged ST without ever activating/set-frontier on ST
    code, payload = _run(
        tmp_path,
        "seed-decision",
        "--section", "I",
        "--lens-tags", "ST",
        "--text", "orphan maturity",
    )
    assert code == 0, payload
    _run(tmp_path, "checkpoint", "--name", "shape")
    # Clear I so pointer coverage isn't the failure mode
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    # I has no facts with lens I — clear would fail; skip I instead
    _run(tmp_path, "skip-section", "--section", "I", "--reason", "n/a")
    code, payload = _run(tmp_path, "recompose-check")
    assert code == 1
    errors = payload.get("recompose_check", {}).get("errors", [])
    assert any("untouched" in e and "ST" in e for e in errors)


def test_update_open_patches_fields(tmp_path):
    _seed(tmp_path, active="ST")
    code, payload = _run(
        tmp_path,
        "add-open",
        "--kw", "2",
        "--trigger", "ai",
        "--means", "ai_scan",
        "--problem", "gap",
        "--leaning", "old",
        "--detected-under", "ST",
    )
    assert code == 0
    oid = payload["id"]
    code, payload = _run(
        tmp_path,
        "update-open",
        "--open-id", oid,
        "--leaning", "new leaning",
        "--provenance-note", "also from intent_baseline",
        "--blocking", "false",
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


def test_deprecated_register_ep_fails(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(
        tmp_path,
        "register-ep",
        "--json",
        json.dumps({"section": "I", "description": "x"}),
    )
    assert code == 1
    assert "removed" in payload["error"].lower() or "REMOVED" in payload["error"]


def test_init_pointer_does_not_create_ep_ledger(tmp_path):
    code, payload = _run(tmp_path, "init-pointer", "--sections", "I,ST", "--mandatory", "")
    assert code == 0, payload
    assert not (tmp_path / "exposed-points.json").exists()
    assert (tmp_path / "inductive-scope" / "_index.json").exists()


def test_check_coverage_passes_when_all_cleared(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "I body")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "clear-section", "--section", "I")
    _run(tmp_path, "activate-section", "--section", "ST")
    _run(tmp_path, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "ST body")
    _run(tmp_path, "set-frontier", "--section", "ST", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "clear-section", "--section", "ST")
    code, payload = _run(tmp_path, "check-coverage")
    assert code == 0, payload
    assert payload.get("ok") is True
    assert "decision_fact_claims" not in payload


def _clear_both_sections(out_dir: Path) -> None:
    _seed(out_dir, active="I")
    _run(out_dir, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "I body")
    _run(out_dir, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(out_dir, "clear-section", "--section", "I")
    _run(out_dir, "activate-section", "--section", "ST")
    _run(out_dir, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "ST body")
    _run(out_dir, "set-frontier", "--section", "ST", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(out_dir, "clear-section", "--section", "ST")


def test_skip_and_list_sections(tmp_path):
    _seed(tmp_path, active="ST")
    code, payload = _run(tmp_path, "skip-section", "--section", "ST", "--reason", "n/a")
    assert code == 0, payload
    code, payload = _run(tmp_path, "list-sections")
    assert code == 0, payload
    assert payload["sections"]["ST"]["status"] == "skipped"


def test_full_section_order_allows_former_peel_seed(tmp_path):
    """Init with registry-wide order → former peel key (CTX) is writable."""
    order = "CTX,GO,SC,NG,I,ST,KD,IF,OQ,VD,OD"
    code, payload = _run(tmp_path, "init-pointer", "--sections", order, "--mandatory", "")
    assert code == 0, payload
    code, payload = _run(tmp_path, "activate-section", "--section", "CTX")
    assert code == 0, payload
    code, payload = _run(
        tmp_path,
        "seed-decision",
        "--section",
        "CTX",
        "--lens-tags",
        "CTX",
        "--text",
        "trigger and impact from upstream",
    )
    assert code == 0, payload
    assert payload["id"] == "F-1"
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert facts[0]["lens_tags"] == ["CTX"]


def test_skip_requires_activate_first(tmp_path):
    """Focus guard: skip without activate fails. Use optional-style key OQ for positive skip."""
    code, payload = _run(tmp_path, "init-pointer", "--sections", "OQ,I", "--mandatory", "")
    assert code == 0, payload
    code, payload = _run(
        tmp_path, "skip-section", "--section", "OQ", "--reason", "no upstream substance"
    )
    assert code == 1 and not payload["ok"]
    assert "focus guard" in payload["error"]
    code, payload = _run(tmp_path, "activate-section", "--section", "OQ")
    assert code == 0, payload
    code, payload = _run(
        tmp_path, "skip-section", "--section", "OQ", "--reason", "no upstream substance"
    )
    assert code == 0, payload
    code, payload = _run(tmp_path, "activate-section", "--section", "I")
    assert code == 0, payload
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "body")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "clear-section", "--section", "I")
    code, payload = _run(tmp_path, "check-coverage")
    assert code == 0, payload
    assert payload.get("ok") is True


def test_required_lens_left_active_is_not_skipped_after_seed_path(tmp_path):
    """Agent contract: required/default lens with no skip stays non-skipped (Exit not fake-closed)."""
    code, payload = _run(tmp_path, "init-pointer", "--sections", "CTX,I", "--mandatory", "")
    assert code == 0, payload
    code, payload = _run(tmp_path, "activate-section", "--section", "CTX")
    assert code == 0, payload
    # No skip: required lens left active for G3 (SKILL discipline; CLI does not enforce presence).
    code, status = _run(tmp_path, "status")
    assert code == 0, status
    assert status["sections"]["CTX"] == "active"
    code, payload = _run(tmp_path, "check-coverage")
    assert code == 1
    assert any("CTX" in e for e in payload.get("errors", []))


def test_add_open_requires_trigger_and_means(tmp_path):
    _seed(tmp_path, active="ST")
    code, payload = _run(
        tmp_path,
        "add-open",
        "--kw", "2",
        "--problem", "状态是否共享？",
    )
    assert code == 1
    assert not payload.get("ok", True)
    assert "trigger" in payload.get("error", "").lower() or "means" in payload.get(
        "error", ""
    ).lower()


def test_defer_open(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "add-open",
        "--kw", "3",
        "--trigger", "human",
        "--means", "human_direct",
        "--problem", "HA later",
        "--blocking", "false",
    )
    code, payload = _run(
        tmp_path,
        "defer-open",
        "--open-id", "O-1",
        "--note", "本轮不展开",
    )
    assert code == 0, payload
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "deferred"
    assert opens[0]["note"] == "本轮不展开"


def test_update_decision_updates_fact(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "seed-decision",
        "--section", "ST",
        "--lens-tags", "ST",
        "--text", "初稿",
    )
    code, payload = _run(
        tmp_path,
        "update-decision",
        "--id", "F-1",
        "--text", "修订稿",
    )
    assert code == 0, payload
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert facts[0]["text"] == "修订稿"


def test_attach_code_refs_open_only(tmp_path):
    _seed(tmp_path, active="ST")
    _run(
        tmp_path,
        "add-open",
        "--kw", "1",
        "--trigger", "ai",
        "--means", "ai_probe",
        "--problem", "gap",
    )
    code, payload = _run(
        tmp_path,
        "attach-code-refs",
        "--id", "O-1",
        "--refs", "gateway/router.go::HTTPIngress (L88)",
    )
    assert code == 0, payload
    assert payload["code_refs"] == ["gateway/router.go::HTTPIngress (L88)"]
    # F- ids rejected
    _run(tmp_path, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "x")
    code, payload = _run(
        tmp_path,
        "attach-code-refs",
        "--id", "F-1",
        "--refs", "x.py:1",
    )
    assert code == 1
    assert "O-" in payload["error"]


def test_view_synthesis_off_assembles_fact_text(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "A-decision")
    _run(tmp_path, "activate-section", "--section", "I")
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "B-decision")
    _run(
        tmp_path,
        "add-open",
        "--kw", "2",
        "--trigger", "ai",
        "--means", "ai_scan",
        "--problem", "should-not-appear-in-off",
        "--blocking", "false",
    )
    code, payload = _run(tmp_path, "view", "--synthesis", "off", "--scope", "all")
    assert code == 0, payload
    md = payload["markdown"]
    assert "A-decision" in md and "B-decision" in md
    assert "should-not-appear-in-off" not in md
    assert "## ST" in md or "# ST" in md


def test_view_synthesis_on_returns_triple_bundle(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "A")
    code, payload = _run(
        tmp_path,
        "view",
        "--synthesis", "on",
        "--scope", "ST",
        "--granularity", "架构大局",
    )
    assert code == 0, payload
    bundle = payload["bundle"]
    assert "index" in bundle
    assert "sections" in bundle
    assert "opens" in bundle
    assert "facts" in bundle
    assert payload["granularity"] == "架构大局"
    assert bundle["sections"][0]["key"] == "ST"
    assert "decisions" not in bundle["sections"][0]
    assert bundle["facts"][0]["id"] == "F-1"


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
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "body")
    _run(tmp_path, "clear-section", "--section", "I")
    code, payload = _run(tmp_path, "recompose-check")
    assert code == 1
    assert payload.get("ok") is False
    errors = payload.get("recompose_check", {}).get("errors", [])
    assert any("shape checkpoint" in e for e in errors)


def test_recompose_check_passes_with_shape_checkpoint(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "I", "--lens-tags", "I", "--text", "body")
    _run(tmp_path, "clear-section", "--section", "I")
    # Also clear ST so coverage is clean — seed ST fact first
    _run(tmp_path, "activate-section", "--section", "ST")
    _run(tmp_path, "set-frontier", "--section", "ST", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "seed-decision", "--section", "ST", "--lens-tags", "ST", "--text", "st")
    _run(tmp_path, "clear-section", "--section", "ST")
    code, ck = _run(tmp_path, "checkpoint", "--name", "shape")
    assert code == 0, ck
    code, payload = _run(tmp_path, "recompose-check")
    assert code == 0, payload
    rc = payload["recompose_check"]
    assert rc["reforms_shape"] is True
    assert rc["shape_absorbed"] is True
    assert rc["errors"] == []
    assert "checkpoint_git_sha" in rc


def test_get_section_returns_slim_maturity(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "set-frontier", "--section", "ST", "--kw", "2")
    code, got = _run(tmp_path, "get-section", "--section", "ST")
    assert code == 0, got
    sec = got["section"]
    assert set(sec.keys()) == {"key", "status", "frontier_kw"}
    assert sec["frontier_kw"] == 2


def test_seed_rejects_empty_lens_tags(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(
        tmp_path,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "",
        "--text",
        "body",
    )
    assert code != 0
    err = str(payload.get("error") or payload.get("raw") or payload)
    assert "lens_tags" in err or "required" in err.lower() or "lens" in err.lower()


def test_seed_rejects_lens_outside_coverage(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(
        tmp_path,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "ZZ",
        "--text",
        "body",
    )
    assert code == 1
    assert "lens" in str(payload.get("error", "")).lower() or "ZZ" in str(
        payload.get("error", "")
    )


def test_add_open_rejects_unknown_detected_under(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(
        tmp_path,
        "add-open",
        "--kw",
        "1",
        "--trigger",
        "ai",
        "--means",
        "ai_probe",
        "--problem",
        "gap",
        "--detected-under",
        "ZZ",
    )
    assert code == 1
    assert "detected_under" in payload.get("error", "")


def test_update_open_rejects_unknown_detected_under(tmp_path):
    _seed(tmp_path, active="I")
    code, add_payload = _run(
        tmp_path,
        "add-open",
        "--kw",
        "1",
        "--trigger",
        "ai",
        "--means",
        "ai_probe",
        "--problem",
        "gap",
        "--detected-under",
        "I",
    )
    assert code == 0, add_payload
    code, payload = _run(
        tmp_path,
        "update-open",
        "--open-id",
        "O-1",
        "--detected-under",
        "ZZ",
    )
    assert code == 1
    assert "detected_under" in payload.get("error", "")
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["detected_under"] == "I"


def _seed_open_for_settle(tmp_path: Path) -> None:
    _seed(tmp_path, active="ST")
    code, add_payload = _run(
        tmp_path,
        "add-open",
        "--kw",
        "1",
        "--trigger",
        "ai",
        "--means",
        "ai_probe",
        "--problem",
        "gap",
    )
    assert code == 0, add_payload


def test_settle_rolls_back_facts_when_opens_save_fails(tmp_path, monkeypatch, capsys):
    """S1: empty facts_before + ValueError → unlink facts; open stays open."""
    import inductive_g3_section_control as ctl

    _seed_open_for_settle(tmp_path)
    assert not (tmp_path / "_facts.json").exists()

    monkeypatch.setattr(
        ctl,
        "_save_opens",
        lambda out_dir, opens: (_ for _ in ()).throw(
            ValueError("simulated opens write failure")
        ),
    )

    facts_after = [
        {
            "id": "F-1",
            "text": "orphan candidate",
            "lens_tags": ["ST"],
            "origin": {"type": "discovered", "ref": ["O-1"]},
        }
    ]
    opens_after = json.loads(
        (tmp_path / "inductive-opens.json").read_text(encoding="utf-8")
    )
    opens_after[0]["status"] = "settled"
    opens_after[0]["resolved_by"] = ["F-1"]

    with pytest.raises(SystemExit) as exc:
        ctl._commit_facts_then_opens(
            tmp_path,
            facts_before=[],
            facts_after=facts_after,
            opens_after=opens_after,
        )
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().out)
    assert err.get("ok") is False
    assert "rolled back" in err.get("error", "")
    assert not (tmp_path / "_facts.json").exists()
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "open"


def test_settle_rolls_back_to_prior_facts_when_opens_fails(tmp_path, monkeypatch, capsys):
    """S1: non-empty facts_before must be restored after opens boom."""
    import inductive_g3_section_control as ctl

    _seed_open_for_settle(tmp_path)
    prior = [
        {
            "id": "F-1",
            "text": "seed fact",
            "lens_tags": ["ST"],
            "origin": {"type": "seed", "ref": ["D-1"]},
        }
    ]
    (tmp_path / "_facts.json").write_text(
        json.dumps(prior, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    monkeypatch.setattr(
        ctl,
        "_save_opens",
        lambda out_dir, opens: (_ for _ in ()).throw(OSError("disk full")),
    )

    facts_after = prior + [
        {
            "id": "F-2",
            "text": "orphan candidate",
            "lens_tags": ["ST"],
            "origin": {"type": "discovered", "ref": ["O-1"]},
        }
    ]
    opens_after = json.loads(
        (tmp_path / "inductive-opens.json").read_text(encoding="utf-8")
    )
    opens_after[0]["status"] = "settled"
    opens_after[0]["resolved_by"] = ["F-2"]

    with pytest.raises(SystemExit) as exc:
        ctl._commit_facts_then_opens(
            tmp_path,
            facts_before=prior,
            facts_after=facts_after,
            opens_after=opens_after,
        )
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().out)
    assert "rolled back" in err.get("error", "")
    restored = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert [f["id"] for f in restored] == ["F-1"]
    assert restored[0]["text"] == "seed fact"
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "open"


def test_settle_rolls_back_on_opens_oserror(tmp_path, monkeypatch, capsys):
    """S1: OSError from opens save (realistic I/O) must trigger facts rollback."""
    import inductive_g3_section_control as ctl

    _seed_open_for_settle(tmp_path)

    monkeypatch.setattr(
        ctl,
        "_save_opens",
        lambda out_dir, opens: (_ for _ in ()).throw(OSError("permission denied")),
    )

    facts_after = [
        {
            "id": "F-1",
            "text": "orphan candidate",
            "lens_tags": ["ST"],
            "origin": {"type": "discovered", "ref": ["O-1"]},
        }
    ]
    opens_after = json.loads(
        (tmp_path / "inductive-opens.json").read_text(encoding="utf-8")
    )
    opens_after[0]["status"] = "settled"
    opens_after[0]["resolved_by"] = ["F-1"]

    with pytest.raises(SystemExit) as exc:
        ctl._commit_facts_then_opens(
            tmp_path,
            facts_before=[],
            facts_after=facts_after,
            opens_after=opens_after,
        )
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().out)
    assert "rolled back" in err.get("error", "")
    assert not (tmp_path / "_facts.json").exists()
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "open"


# --- facet seeds (string[] reminders; no clear gate) -----------------------

_OPS_SECTION_REGISTRY = {
    "version": "1",
    "section_order": ["I", "OPS"],
    "document_preamble": "test",
    "sections": {
        "I": {
            "heading": "Intent",
            "intent": "intent",
            "upstream": [],
            "relations": {},
        },
        "OPS": {
            "heading": "Ops",
            "intent": "operability",
            "upstream": [],
            "relations": {},
            "facets": [
                "runtime degradation",
                "steady-state rollback",
            ],
        },
    },
}


def test_clear_ops_ok_without_facet_receipts(tmp_path):
    """Seeds are not a clear gate: one OPS fact is enough for facet purposes."""
    code, payload = _run(
        tmp_path, "init-pointer", "--sections", "OPS,I", "--mandatory", ""
    )
    assert code == 0, payload
    _run(tmp_path, "activate-section", "--section", "OPS")
    (tmp_path / "section-registry.json").write_text(
        json.dumps(_OPS_SECTION_REGISTRY, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    code, p = _run(
        tmp_path,
        "seed-decision",
        "--section",
        "OPS",
        "--lens-tags",
        "OPS",
        "--text",
        "operability stance for this demand",
    )
    assert code == 0, p
    _run(tmp_path, "set-frontier", "--section", "OPS", "--kw", "1")
    code, payload = _run(
        tmp_path, "clear-section", "--section", "OPS", "--target-kw", "1"
    )
    assert code == 0, payload


def test_add_open_without_facet_id(tmp_path):
    code, payload = _run(
        tmp_path, "init-pointer", "--sections", "OPS,I", "--mandatory", ""
    )
    assert code == 0, payload
    _run(tmp_path, "activate-section", "--section", "OPS")
    (tmp_path / "section-registry.json").write_text(
        json.dumps(_OPS_SECTION_REGISTRY, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    code, payload = _run(
        tmp_path,
        "add-open",
        "--kw",
        "1",
        "--trigger",
        "ai",
        "--means",
        "ai_scan",
        "--problem",
        "gap",
        "--detected-under",
        "OPS",
    )
    assert code == 0, payload


def test_materialize_section_registry_from_source(tmp_path):
    _seed(tmp_path, active="I")
    src = tmp_path / "src-registry.json"
    src.write_text(
        json.dumps(_OPS_SECTION_REGISTRY, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    local = tmp_path / "section-registry.json"
    if local.exists():
        local.unlink()
    code, payload = _run(
        tmp_path,
        "materialize-section-registry",
        "--source",
        str(src),
    )
    assert code == 0, payload
    assert (tmp_path / "section-registry.json").is_file()
    assert "OPS" in payload.get("seed_lenses", [])

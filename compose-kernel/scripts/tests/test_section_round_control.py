#!/usr/bin/env python3
"""Tests for section_round_control.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import CORE, SECTION  # noqa: E402

from section_round_control import (  # noqa: E402
    _normalize_section,
    round_probe_input,
)
from test_registry_fixtures import (  # noqa: E402
    first_section_key,
    minimal_compose_doc_markdown,
    second_section_key,
    section_headings_map,
    section_key_at,
    third_section_key,
)

import bootstrap  # noqa: F401
from bootstrap import CORE, SECTION  # noqa: E402

_SCRIPT = SECTION / "section_round_control.py"
_CYCLE_ID = "test-cycle"
from test_template_data import LEGACY_SECTION_REGISTRY, seed_template_cache  # noqa: E402
from workflow_paths import seed_profile_pointer_for_tests  # noqa: E402


def _seed_registry_cache(project_root: Path) -> None:
    seed_template_cache(
        project_root,
        "tech-plan",
        "tpt_section_registry_url",
        LEGACY_SECTION_REGISTRY,
    )


def _setup_cycle(tmp_path: Path) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE_ID, "tech-plan")
    _seed_registry_cache(tmp_path)
    cycle_dir = tmp_path / ".cache/cursor/lulu-dev-workflow" / _CYCLE_ID
    plan_base = cycle_dir / "tech" / "plan"
    revision = plan_base / "revision1"
    revision.mkdir(parents=True)
    (plan_base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    (revision / "tech-doc.md").write_text(minimal_compose_doc_markdown(), encoding="utf-8")
    (revision / "drafting-progress.md").write_text(
        f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\n"
        "current_step: RoundIteration\nround: 1\n---\n",
        encoding="utf-8",
    )
    diag_dir = cycle_dir / "tech" / "diagnostic"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433
    from init_drafting_helpers import tech_plan_scope_refs  # noqa: WPS433
    from workflow_state_schema import init_drafting  # noqa: WPS433

    refs = [DeliveredRef(type="tech-diagnostic", path=str(decision.resolve()))]
    init_drafting(
        revision / "workflow-state.md",
        mode="tech",
        delivered_refs=refs,
        scope_refs=tech_plan_scope_refs(refs),
    )
    return cycle_dir


def _run_fail(cycle_dir: Path, *args: str, round_n: str | None = "1") -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_SCRIPT), "--cycle-dir", str(cycle_dir)]
    if round_n is not None:
        cmd.extend(["--round", round_n])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def _run(cycle_dir: Path, *args: str, round_n: str | None = "1") -> dict:
    cmd = [sys.executable, str(_SCRIPT), "--cycle-dir", str(cycle_dir)]
    if round_n is not None:
        cmd.extend(["--round", round_n])
    cmd.extend(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_normalize_section_aliases():
    headings = section_headings_map()
    first = first_section_key()
    second = second_section_key()
    assert _normalize_section(headings[first].lower()) == first
    assert _normalize_section(second) == second
    assert _normalize_section(third_section_key()) == third_section_key()


def test_read_section_body(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    first = first_section_key()
    result = _run(cycle_dir, "read-section-body", "--section", first, round_n=None)
    assert result["ok"] is True
    assert result["section_key"] == first
    assert first in result["body"]
    assert "section-key:" in (cycle_dir / "tech" / "plan" / "revision1" / "tech-doc.md").read_text()


def test_read_context(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    ctx = _run(cycle_dir, "read-context", round_n=None)
    assert ctx["round"] == 1
    assert (cycle_dir / "tech" / "plan" / "anchor-ledger.md").exists()
    assert ctx["scope_doc_path"].endswith("tech/diagnostic/decision-doc.md")


def test_read_context_uses_scope_refs_primary_not_product(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    revision = cycle_dir / "tech" / "plan" / "revision1"
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433
    from workflow_state_schema import init_drafting, load_workflow_state, save_workflow_state  # noqa: WPS433

    product_doc = tmp_path / "product-doc.md"
    product_doc.write_text("# Product\n", encoding="utf-8")
    decision_doc = Path(
        cycle_dir / "tech" / "diagnostic" / "decision-doc.md",
    )
    ws = revision / "workflow-state.md"
    state = load_workflow_state(ws)
    state["delivered_refs"] = (
        '[{"type":"product-spec","path":"'
        + str(product_doc.resolve())
        + '"},{"type":"tech-diagnostic","path":"'
        + str(decision_doc.resolve())
        + '"}]'
    )
    save_workflow_state(ws, state, merge=True)
    ctx = _run(cycle_dir, "read-context", round_n=None)
    assert ctx["scope_doc_path"] == str(decision_doc.resolve())
    assert any(r["type"] == "product-spec" for r in ctx["delivered_refs"])


def test_read_context_scope_primary_design_doc(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    revision = cycle_dir / "tech" / "plan" / "revision1"
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433
    from init_drafting_helpers import tech_plan_scope_refs  # noqa: WPS433
    from workflow_state_schema import init_drafting  # noqa: WPS433

    design_doc = tmp_path / "design-doc.md"
    design_doc.write_text("# Design\n", encoding="utf-8")
    refs = [DeliveredRef(type="tech-design", path=str(design_doc.resolve()))]
    init_drafting(
        revision / "workflow-state.md",
        mode="tech",
        delivered_refs=refs,
        scope_refs=tech_plan_scope_refs(refs),
    )
    ctx = _run(cycle_dir, "read-context", round_n=None)
    assert ctx["scope_doc_path"] == str(design_doc.resolve())


def test_read_context_fails_without_workflow_state(tmp_path: Path):
    _seed_registry_cache(tmp_path)
    seed_profile_pointer_for_tests(tmp_path, _CYCLE_ID, "tech-plan")
    cycle_dir = tmp_path / ".cache/cursor/lulu-dev-workflow" / _CYCLE_ID
    plan_base = cycle_dir / "tech" / "plan"
    revision = plan_base / "revision1"
    revision.mkdir(parents=True)
    (plan_base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    (revision / "tech-doc.md").write_text(minimal_compose_doc_markdown(), encoding="utf-8")
    (revision / "drafting-progress.md").write_text(
        f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\n"
        "current_step: RoundIteration\nround: 1\n---\n",
        encoding="utf-8",
    )
    proc = _run_fail(cycle_dir, "read-context", round_n=None)
    assert proc.returncode != 0
    assert "workflow-state not found" in proc.stderr


def test_read_context_fails_when_scope_doc_missing(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    revision = cycle_dir / "tech" / "plan" / "revision1"
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433
    from workflow_state_schema import init_drafting  # noqa: WPS433

    missing = tmp_path / "missing-decision.md"
    init_drafting(
        revision / "workflow-state.md",
        mode="tech",
        delivered_refs=[DeliveredRef(type="tech-diagnostic", path=str(missing))],
        scope_refs=[DeliveredRef(type="tech-diagnostic", path=str(missing))],
    )
    proc = _run_fail(cycle_dir, "read-context", round_n=None)
    assert proc.returncode != 0
    assert "scope doc not found" in proc.stderr


def test_append_skip_any_section(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "--round",
            "1",
            "append-skip",
            "--section",
            first_section_key(),
            "--kw-gap",
            "KW1",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


def test_append_skip_empty_notes_roundtrip(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "append-skip", "--section", second_section_key(), "--kw-gap", "KW2")
    ctx = _run(cycle_dir, "read-context", round_n=None)
    assert len(ctx["skips"]) == 1
    assert ctx["skips"][0]["kw_gap"] == "KW2"


def test_update_anchor_status(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    result = _run(
        cycle_dir,
        "append-anchor",
        "--section",
        second_section_key(),
        "--criterion",
        "must be idempotent",
    )
    anchor_id = result["id"]
    _run(cycle_dir, "update-anchor-status", "--id", anchor_id, "--status", "failing", round_n=None)
    ctx = _run(cycle_dir, "read-context", round_n=None)
    assert ctx["anchors"][0]["status"] == "failing"
    conv = _run(cycle_dir, "check-convergence", "--no-accept", "--gaps-resolved", round_n=None)
    assert conv["converged"] is False
    assert "anchor" in conv["reason"]


def test_check_convergence_requires_pointer_when_round_dir_exists(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    revision = cycle_dir / "tech" / "plan" / "revision1"
    (revision / "round-1").mkdir()
    result = _run(cycle_dir, "check-convergence", "--no-accept", "--gaps-resolved", round_n=None)
    assert result["converged"] is False
    assert "pointer" in result["reason"]


def test_check_convergence_converged(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    result = _run(cycle_dir, "check-convergence", "--no-accept", "--gaps-resolved", round_n=None)
    assert result["converged"] is True
    assert result["reason"] == "ok"


_KW_CRITERIA = {
    "kw0": "阶段未命名",
    "kw1": "能说出执行分为哪些阶段",
    "kw2": "能说出每个阶段的 Done 判据",
    "kw3": "能说出进入下一阶段的前提条件",
    "kw4": "能说出阶段边界未达成时如何决策",
}


def _sample_probe_json(*, section_key: str | None = None) -> str:
    key = section_key or first_section_key()
    headings = section_headings_map()
    heading = headings[key]
    payload = {
        "version": "3",
        "kind": "probe",
        "round": 1,
        "revision": 1,
        "cycle_id": _CYCLE_ID,
        "section_key": key,
        "section": heading,
        "probe_seq": 1,
        "anchor_failures": [],
        "anchor_candidates": [],
        "items": [
            {
                "id": f"{key}-1",
                "gap_kind": "kw",
                "scope": "subsection",
                "section_key": key,
                "section": heading,
                "target_kw": 2,
                "intent_gap": "每个阶段缺少 Done 判据",
                "kw_criteria": _KW_CRITERIA,
                "sub_section_summary": "phase plan",
                "sub_section_text": "deps only",
                "skip_key": f"{key}:phase-plan",
                "status": "open",
                "decision": "—",
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def test_init_round_dir_and_pointer(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    first = first_section_key()
    fourth = section_key_at(3)
    result = _run(cycle_dir, "init-round-dir")
    assert result["active_section"] == first
    pointer = _run(cycle_dir, "read-section-pointer")
    assert pointer["sections"][first]["status"] == "active"
    assert pointer["sections"][fourth]["status"] == "pending"


def test_write_and_read_probe_report(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "init-round-dir")
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "write-probe-report",
            "--json",
            _sample_probe_json(section_key=first_section_key()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    written = json.loads(proc.stdout)
    assert written["probe_seq"] == 1
    assert written["open_count"] == 1

    first = first_section_key()
    report = _run(cycle_dir, "read-probe-report")
    assert report["section_key"] == first
    assert report["items"][0]["id"] == f"{first}-1"

    gap = _run(cycle_dir, "read-gap-report")
    assert gap["active_section"] == first
    assert gap["open_count"] == 1


def test_advance_and_rewind_section(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "init-round-dir")
    subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "write-probe-report",
            "--json",
            _sample_probe_json(section_key=first_section_key()),
        ],
        check=True,
    )
    first = first_section_key()
    second = second_section_key()
    _run(cycle_dir, "mark-section-stable", "--section", first)
    advanced = _run(cycle_dir, "advance-section")
    assert advanced["active_section"] == second

    rewound = _run(cycle_dir, "rewind-section", "--to", first)
    assert rewound["active_section"] == first
    pointer = _run(cycle_dir, "read-section-pointer")
    assert pointer["sections"][second]["status"] == "invalidated"


def test_probe_read_gap_item_and_update(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "init-round-dir")
    subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "write-probe-report",
            "--json",
            _sample_probe_json(section_key=first_section_key()),
        ],
        check=True,
    )
    first = first_section_key()
    item = _run(cycle_dir, "read-gap-item", "--id", f"{first}-1")
    assert item["refiner"]["intent_gap"] == "每个阶段缺少 Done 判据"
    assert item["item"]["gap_kind"] == "kw"
    _run(
        cycle_dir,
        "update-gap-decision",
        "--id",
        f"{first_section_key()}-1",
        "--decision",
        "skip",
    )
    ctx = _run(cycle_dir, "read-context", round_n=None)
    assert len(ctx["skips"]) == 1


def test_skip_clears_undecided_count(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "init-round-dir")
    subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "write-probe-report",
            "--json",
            _sample_probe_json(section_key=first_section_key()),
        ],
        check=True,
    )
    before = _run(cycle_dir, "read-probe-report")
    assert before["undecided_count"] == 1
    _run(
        cycle_dir,
        "update-gap-decision",
        "--id",
        f"{first_section_key()}-1",
        "--decision",
        "skip",
    )
    after = _run(cycle_dir, "read-probe-report")
    assert after["open_count"] == 1
    assert after["undecided_count"] == 0


def test_init_round_dir_idempotent(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    first = first_section_key()
    first_result = _run(cycle_dir, "init-round-dir")
    second = _run(cycle_dir, "init-round-dir")
    assert first_result["active_section"] == first
    assert second["already_initialized"] is True
    assert second["active_section"] == first


def test_write_refiner_artifact(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "init-round-dir")
    first = first_section_key()
    payload = json.dumps(
        {
            "version": "1",
            "kind": "refiner",
            "round": 1,
            "revision": 1,
            "cycle_id": _CYCLE_ID,
            "section_key": first,
            "gap_item_id": f"{first}-1",
            "intent_gap": "缺少 Why",
            "confirmed_draft": "Build faster because ...",
            "draft_turns": 2,
        },
        ensure_ascii=False,
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "write-refiner-artifact",
            "--json",
            payload,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["gap_item_id"] == f"{first}-1"
    assert f"refiner-001-{first}-1.json" in result["path"]


class TestRoundProbeInput:
    def test_returns_dispatch_input_in_round_iteration(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        revision = cycle_dir / "tech" / "plan" / "revision1"
        _run(cycle_dir, "init-round-dir")
        result = round_probe_input(cycle_dir)
        assert result["ok"] is True
        assert "dispatch_input" in result
        inp = result["dispatch_input"]
        assert f"CYCLE_ID:         {_CYCLE_ID}" in inp
        assert "CYCLE_TYPE" not in inp
        assert "ROUND_N:          1" in inp
        assert "COMPOSE_DOC_PATH:" in inp
        assert f"ACTIVE_SECTION: {first_section_key()}" in inp
        assert "ROUND_DIR:" in inp
        assert revision.resolve().as_posix() in inp
        assert "tech-doc.md" in inp

    def test_round_2_reflects_advanced_round(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        progress = cycle_dir / "tech" / "plan" / "revision1" / "drafting-progress.md"
        progress.write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\n"
            "current_step: RoundIteration\nround: 2\n---\n",
            encoding="utf-8",
        )
        _run(cycle_dir, "init-round-dir", round_n="2")
        result = round_probe_input(cycle_dir)
        assert result["ok"] is True
        assert "ROUND_N:          2" in result["dispatch_input"]

    def test_fails_when_ready_not_round_iteration(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        progress = cycle_dir / "tech" / "plan" / "revision1" / "drafting-progress.md"
        progress.write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\ncurrent_step: Ready\n---\n",
            encoding="utf-8",
        )
        result = round_probe_input(cycle_dir)
        assert result["ok"] is False
        assert "RoundIteration" in result["reason"]

    def test_fails_without_progress(self, tmp_path: Path):
        cycle_dir = tmp_path / "empty-cycle"
        plan_base = cycle_dir / "tech" / "plan"
        revision = plan_base / "revision1"
        revision.mkdir(parents=True)
        (plan_base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        result = round_probe_input(cycle_dir)
        assert result["ok"] is False

    def test_fails_without_section_pointer(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        result = round_probe_input(cycle_dir)
        assert result["ok"] is False
        assert "init-round-dir" in result["reason"]

    def test_cli_plaintext_stdout(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        revision = cycle_dir / "tech" / "plan" / "revision1"
        _run(cycle_dir, "init-round-dir")
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-dir",
                str(cycle_dir),
                "round-probe-input",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert proc.stdout.startswith("CYCLE_DIR:")
        assert f"CYCLE_ID:         {_CYCLE_ID}" in proc.stdout
        assert "ROUND_N:          1" in proc.stdout
        assert "COMPOSE_DOC_PATH:" in proc.stdout
        assert "TECH_DOC_PATH:" not in proc.stdout
        assert revision.resolve().as_posix() in proc.stdout
        try:
            json.loads(proc.stdout)
            raise AssertionError("expected plain-text stdout, not JSON")
        except json.JSONDecodeError:
            pass

    def test_cli_failure_json_stdout(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        progress = cycle_dir / "tech" / "plan" / "revision1" / "drafting-progress.md"
        progress.write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\ncurrent_step: Ready\n---\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-dir",
                str(cycle_dir),
                "round-probe-input",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False

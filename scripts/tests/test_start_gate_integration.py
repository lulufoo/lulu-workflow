#!/usr/bin/env python3
"""Tests for t8b: start.py gate integration (check_gate, re-open, back-fill, get_topic_doc).

All start entrypoints (lulu-spec, lulu-plan, lulu-tasks, lulu-code, decision) must
integrate check_gate, current_effective_delivered, invalidate_downstream, and get_topic_doc
before creating a new session.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_LDEV = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _LDEV / "config"

_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}
_CYCLE_ID = "20260524143022-02cd7e6e"
_TOPIC_ID = "topic-20260101000000-deadbeef"

_COMPOSE_START_STAGES = frozenset({"lulu-plan", "lulu-spec"})
_KERNEL_START = _LDEV / "compose" / "scripts" / "session" / "start.py"

_STAGES_WITH_GATE = ["lulu-spec", "lulu-plan", "lulu-tasks", "lulu-code"]
_ALL_STAGES = ["decision", "lulu-spec", "lulu-plan", "lulu-tasks", "lulu-code"]
# decision performs no topic_id/get_topic_ref validation of its own — that check now
# lives entirely in the holder's own resolver (lulu-bet/lulu-approach resolve_context.py)
# or the compose adapter's resolve_norm_constraint_refs, never in the shared kernel itself.
_STAGES_VALIDATING_TOPIC_LINKAGE = ["lulu-spec", "lulu-plan", "lulu-tasks", "lulu-code"]

# Feature cycle order (matches config/transition-table.json)
_FEATURE_CYCLE = [
    "lulu-bet", "lulu-spec", "lulu-approach",
    "lulu-plan", "lulu-tasks", "lulu-code",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start_py(stage: str) -> Path:
    if stage in _COMPOSE_START_STAGES:
        return _KERNEL_START
    return _LDEV / stage / "scripts" / ({"lulu-code": "tc_start.py", "decision": "dec_start.py", "lulu-tasks": "tt_start.py"}.get(stage, "start.py"))


def _scripts_dir(stage: str) -> Path:
    if stage in _COMPOSE_START_STAGES:
        return _KERNEL_START.parent
    return _LDEV / stage / "scripts"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def _make_cycles_json(cache_dir: Path, cycle_id: str, extra: dict = None, name: str = "Test Cycle") -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj = cache_dir / "cycles.json"
    data = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    meta = {"name": name}
    if extra:
        meta.update(extra)
    data[cycle_id] = meta
    cj.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_session_state(cache_dir: Path, cycle_id: str, stage: str, active: int = 1) -> Path:
    """Create session-state.md v2 so start.py increments to the NEXT revision."""
    sys.path.insert(0, str(_LDEV / "scripts"))
    from workflow_sessions import stage_subdir
    p = cache_dir / cycle_id / stage_subdir(stage) / "session-state.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\n"
        "version: 2\n"
        f"active_doc: {active}\n"
        "profile_path: /tmp/compose-profile.json\n"
        f"profile_digest: {'a' * 64}\n"
        "start_id: test-start\n"
        "holder_finalized: true\n"
        "updated_at: 2026-06-01T00:00:00Z\n"
        "---\n",
        encoding="utf-8",
    )
    return p


def _make_cycle_state(cache_dir: Path, cycle_id: str, stage: str) -> Path:
    """Create cycle-state.json for the new transition-table gate."""
    p = cache_dir / cycle_id / "cycle-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"current_stage": stage, "updated_at": "2026-06-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    return p


def _make_session(
    cache_dir: Path,
    cycle_id: str,
    stage: str,
    revision: str,
    state: str,
    updated_at: str = "2026-06-01T00:00:00+00:00",
) -> Path:
    """Create a session state file at the correct path (subdir + revision naming)."""
    sys.path.insert(0, str(_LDEV / "scripts"))
    from workflow_sessions import STAGE_FLAT, stage_subdir
    subdir = stage_subdir(stage)
    if stage in STAGE_FLAT:
        session_dir = cache_dir / cycle_id / subdir
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "session-state.md"
    else:
        import re as _re
        rev_name = (
            f"revision{revision.lstrip('r')}"
            if _re.match(r"^r\d+$", revision)
            else revision
        )
        session_dir = cache_dir / cycle_id / subdir / rev_name
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
    if ws.name == "workflow-state.md" and stage in _COMPOSE_START_STAGES:
        mode = "product" if stage == "lulu-spec" else "tech"
        ws.write_text(
            f"---\n"
            f"version: 1\n"
            f"workflow: tech-doc\n"
            f"mode: {mode}\n"
            f"cycle_type: feature\n"
            f"current_state: {state}\n"
            f"evaluate_round: 0\n"
            f"delivered_refs: []\n"
            f"updated_at: {updated_at}\n"
            f"---\n",
            encoding="utf-8",
        )
        _make_session_state(cache_dir, cycle_id, stage, active=int(revision.lstrip("r") or "1"))
        return ws
    ws.write_text(
        f"---\ncurrent_state: {state}\nupdated_at: {updated_at}\n---\n",
        encoding="utf-8",
    )
    return ws


def _write_scope_package(tmp_path: Path, source: Path | None = None) -> Path:
    src = source if source is not None else (tmp_path / "scope-source.md")
    if not src.is_file():
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("# scope\n", encoding="utf-8")
    resolved = src.resolve()
    path = tmp_path / "scope-package.json"
    path.write_text(
        json.dumps({"version": 2, "source_path": str(resolved)}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path.resolve()


def _compose_start_args(
    profile_id: str,
    tmp_path: Path,
    source: Path | None = None,
    *extra: str,
) -> list[str]:
    scope = _write_scope_package(tmp_path, source)
    return [
        "--profile-path",
        str(_LDEV / profile_id / "compose-profile.json"),
        "--scope-package",
        str(scope),
        *extra,
    ]


def _start_payload(result: subprocess.CompletedProcess) -> dict:
    text = (result.stdout or "").strip()
    return json.loads(text) if text.startswith("{") else {}


def _assert_gate_blocked(result: subprocess.CompletedProcess, stage: str) -> None:
    assert result.returncode == 1, result.stderr or result.stdout
    if stage in _COMPOSE_START_STAGES:
        payload = _start_payload(result)
        assert payload.get("ok") is False, result.stdout
        assert payload.get("code") == "gate_blocked", result.stdout
        return
    assert "Gate blocked" in result.stderr


def _assert_start_ok(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode == 0, result.stderr or result.stdout
    payload = _start_payload(result)
    if payload:
        assert payload.get("ok") is True, result.stdout
    return payload


def _assert_topic_unresolved(result: subprocess.CompletedProcess, stage: str) -> None:
    assert result.returncode == 1, result.stderr or result.stdout
    if stage not in _COMPOSE_START_STAGES:
        return
    payload = _start_payload(result)
    assert payload.get("code") == "topic_unresolved", result.stdout
    assert "topic" in str(payload.get("error", "")).lower()


def _seed_decision_config(tmp_path: Path) -> None:
    """Seed workflow-config + local decision-doc template for dec_start init-session."""
    cfg_dir = tmp_path / ".github" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Readiness\n\nTBD\n\n## 4. Direction Comparison\n\nTBD\n\n"
        "## 5. Settled Direction\n\n"
        "### Decision Rationale\n\nTBD\n\n"
        "### Scope\n\n"
        "**Applies to:** TBD\n\n"
        "**Explicitly excludes:** TBD\n\n"
        "### Landing Approach\n\nTBD\n\n"
        "## 6. Assumptions & Risks\n\nTBD\n\n"
        "## 7. Execution Analysis\n\n### 7.1 Acceptance Criteria\n\nTBD\n",
        encoding="utf-8",
    )
    (cfg_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )


def _diag_holder_args(stage: str = "lulu-bet") -> list[str]:
    return [
        "--constraints",
        str(_LDEV / stage / "constraints-feature.json"),
    ]


def _stage_extra_args(stage: str, tmp_path: Path) -> list:
    """Required extra CLI args for each stage start.py."""
    if stage == "decision":
        return _diag_holder_args("lulu-bet")
    if stage == "lulu-spec":
        return _compose_start_args("lulu-spec", tmp_path)
    if stage == "lulu-plan":
        return _compose_start_args("lulu-plan", tmp_path)
    if stage == "lulu-tasks":
        tech_ref = tmp_path / "tech-doc.md"
        tech_ref.write_text("# Tech Doc\n", encoding="utf-8")
        return ["--tech-ref", str(tech_ref)]
    if stage == "lulu-code":
        return []
    return []


def _seed_work_order_handoff(cache_dir: Path, cycle_id: str, active_doc: int = 1) -> None:
    wo_dir = cache_dir / cycle_id / "lulu-tasks"
    wo_dir.mkdir(parents=True, exist_ok=True)
    (wo_dir / "session-state.md").write_text(
        f"---\nactive_doc: {active_doc}\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    r_dir = wo_dir / f"r{active_doc}"
    r_dir.mkdir(parents=True, exist_ok=True)
    (r_dir / "task-list.md").write_text(
        "# Task List\n\n"
        "| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| t1 | test task | `scripts/foo.py` | — | 否 |\n",
        encoding="utf-8",
    )


def _upsert_delivered_ref_entry(
    cache_dir: Path,
    cycle_id: str,
    *,
    delivered_type: str,
    path: Path,
    profile_id: str,
    artifact: str | None = None,
) -> None:
    refs_path = cache_dir / cycle_id / "delivered-refs.json"
    data = (
        json.loads(refs_path.read_text(encoding="utf-8"))
        if refs_path.is_file()
        else {"version": 1, "entries": {}}
    )
    entries = dict(data.get("entries") or {})
    entries[delivered_type] = {
        "delivered_type": delivered_type,
        "path": str(path.resolve()),
        "revision": 1,
        "profile_id": profile_id,
        "delivered_at": "2026-06-01T00:00:00+00:00",
        "source_workflow_state": "",
    }
    if artifact is not None:
        entries[delivered_type]["artifact"] = artifact
    data["entries"] = entries
    refs_path.parent.mkdir(parents=True, exist_ok=True)
    refs_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_product_spec_delivered_refs(
    cache_dir: Path,
    cycle_id: str,
    project_root: Path,
) -> None:
    """Seed delivered-refs.json entries required for lulu-spec start."""
    del project_root
    diag_dir = cache_dir / cycle_id / "lulu-bet"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision_doc = diag_dir / "decision-doc.md"
    if not decision_doc.is_file():
        decision_doc.write_text("# Decision\n", encoding="utf-8")
    decision = diag_dir / "decision-package.json"
    if not decision.is_file():
        decision.write_text(
            json.dumps(
                {
                    "version": 2,
                    "status": "package_ready",
                    "main": {"decision_doc_path": "decision-doc.md"},
                }
            ),
            encoding="utf-8",
        )
    _upsert_delivered_ref_entry(
        cache_dir,
        cycle_id,
        delivered_type="lulu-bet",
        path=decision,
        profile_id="lulu-bet",
        artifact="decision-package",
    )


def _seed_tech_plan_delivered_refs(
    cache_dir: Path,
    cycle_id: str,
    project_root: Path,
    *,
    design_path: Path | None = None,
) -> None:
    """Seed delivered-refs.json entries required for lulu-plan start (tech mode)."""
    del project_root
    diag_dir = cache_dir / cycle_id / "lulu-approach"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision_doc = diag_dir / "decision-doc.md"
    if not decision_doc.is_file():
        decision_doc.write_text("# Decision\n", encoding="utf-8")
    decision = diag_dir / "decision-package.json"
    if not decision.is_file():
        decision.write_text(
            json.dumps(
                {
                    "version": 2,
                    "status": "package_ready",
                    "main": {"decision_doc_path": "decision-doc.md"},
                }
            ),
            encoding="utf-8",
        )
    _upsert_delivered_ref_entry(
        cache_dir,
        cycle_id,
        delivered_type="lulu-approach",
        path=decision,
        profile_id="lulu-approach",
        artifact="decision-package",
    )
    if design_path is not None:
        _upsert_delivered_ref_entry(
            cache_dir,
            cycle_id,
            delivered_type="lulu-design",
            path=design_path,
            profile_id="lulu-design",
        )


def _run_start(
    stage: str,
    tmp_path: Path,
    cycle_id: str = _CYCLE_ID,
    extra_args: list = None,
) -> subprocess.CompletedProcess:
    args = extra_args if extra_args is not None else _stage_extra_args(stage, tmp_path)
    if stage == "lulu-code":
        _seed_work_order_handoff(_cache_dir(tmp_path), cycle_id)
    if stage == "decision":
        _seed_decision_config(tmp_path)
    if stage == "lulu-spec":
        _seed_product_spec_delivered_refs(_cache_dir(tmp_path), cycle_id, tmp_path)
    if stage == "lulu-plan":
        _seed_tech_plan_delivered_refs(_cache_dir(tmp_path), cycle_id, tmp_path)
    cmd = [
        sys.executable, str(_start_py(stage)),
        "--project-root", str(tmp_path),
        "--cycle-id", cycle_id,
    ] + args
    return subprocess.run(
        cmd, capture_output=True, text=True, env=_ENV_COPILOT,
        cwd=str(_scripts_dir(stage)),
    )


def _all_prior_delivered(cache_dir: Path, cycle_id: str, to_stage: str) -> None:
    """Create Delivered sessions for all stages prior to to_stage and update cycle-state.json."""
    if to_stage not in _FEATURE_CYCLE:
        return
    idx = _FEATURE_CYCLE.index(to_stage)
    prior = _FEATURE_CYCLE[:idx]
    for s in prior:
        _make_session(cache_dir, cycle_id, s, "r1", "Delivered")
    if prior:
        _make_cycle_state(cache_dir, cycle_id, prior[-1])


# ---------------------------------------------------------------------------
# TestGateBlocked
# ---------------------------------------------------------------------------

class TestGateBlocked:
    def test_prior_drafting_exits_1(self, tmp_path):
        """Gate blocked: prior stage Drafting → exit 1 with 'Gate blocked' on stderr."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Working")
        result = _run_start("lulu-spec", tmp_path)
        _assert_gate_blocked(result, "lulu-spec")

    def test_gate_blocked_no_session_created(self, tmp_path):
        """Gate blocked → lulu-spec session file not created."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Working")
        _run_start("lulu-spec", tmp_path)
        spec_dir = cd / _CYCLE_ID / "lulu-spec"
        assert not spec_dir.exists() or not any(spec_dir.rglob("workflow-state.md"))

    def test_intermediate_drafting_blocks_downstream(self, tmp_path):
        """Intermediate stage Drafting blocks further downstream stages."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_session(cd, _CYCLE_ID, "lulu-spec", "r1", "Working")
        result = _run_start("lulu-plan", tmp_path)
        _assert_gate_blocked(result, "lulu-plan")


# ---------------------------------------------------------------------------
# TestGatePasses
# ---------------------------------------------------------------------------

class TestGatePasses:
    def test_first_stage_product_diagnostic_allowed(self, tmp_path):
        """No cycle-state.json: lulu-bet (first stage) is allowed."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        result = _run_start(
            "decision",
            tmp_path,
            extra_args=_diag_holder_args("lulu-bet"),
        )
        assert result.returncode == 0, result.stderr

    def test_null_blocks_product_plan(self, tmp_path):
        """No cycle-state.json: lulu-spec is not the first stage → blocked."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        result = _run_start("lulu-spec", tmp_path)
        _assert_gate_blocked(result, "lulu-spec")

    def test_prior_delivered_allows_product_plan(self, tmp_path):
        """lulu-bet Delivered + cycle-state.json set → lulu-spec allowed."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)

    def test_all_prior_delivered_tech_plan(self, tmp_path):
        """All prior stages Delivered + cycle-state.json set → lulu-plan gate passes."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _all_prior_delivered(cd, _CYCLE_ID, "lulu-plan")
        result = _run_start("lulu-plan", tmp_path)
        _assert_start_ok(result)

    def test_start_freezes_and_resolves_refs(self, tmp_path):
        """start.py freezes ① delivered-refs.json copy and materializes ② resolved-refs.json."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _all_prior_delivered(cd, _CYCLE_ID, "lulu-plan")
        design_dir = tmp_path / "design" / "revision1"
        design_doc = design_dir / "execution" / "design-doc.md"
        design_doc.parent.mkdir(parents=True)
        design_doc.write_text("# Design\n", encoding="utf-8")
        design = design_dir / "design-package.json"
        design.write_text(
            json.dumps(
                {
                    "version": 2,
                    "profile_id": "lulu-design",
                    "doc_path": "execution/design-doc.md",
                }
            ),
            encoding="utf-8",
        )
        _seed_tech_plan_delivered_refs(cd, _CYCLE_ID, tmp_path, design_path=design)
        result = _run_start(
            "lulu-plan",
            tmp_path,
            extra_args=_compose_start_args("lulu-plan", tmp_path, design_doc),
        )
        _assert_start_ok(result)
        revision = cd / _CYCLE_ID / "lulu-plan" / "revision1"
        # ① frozen full copy of the cycle delivered-refs.json (audit baseline)
        frozen = json.loads((revision / "delivered-refs.json").read_text(encoding="utf-8"))
        assert frozen["entries"]["lulu-design"]["path"] == str(design.resolve())
        # ② compose kernel writes one scope-package; holder already unwrapped design
        resolved = json.loads((revision / "resolved-refs.json").read_text(encoding="utf-8"))
        assert resolved["scope_ref"]["type"] == "scope-package"
        assert resolved["scope_ref"]["path"] == str(
            (revision / "scope-package.json").resolve()
        )

    def test_decision_always_passes(self, tmp_path):
        """decision stage not in cycle → gate always OK."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        result = _run_start("decision", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_topic_doc_reported_not_merged_into_norm_refs(self, tmp_path):
        """Delivered topic blueprint is reported on start stdout; compose writes empty norm refs."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _make_cycles_json(cd, _TOPIC_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        _seed_product_spec_delivered_refs(cd, _CYCLE_ID, tmp_path)
        topic_doc = tmp_path / "topic-product-doc.md"
        topic_doc.write_text("# Topic Product Doc\n", encoding="utf-8")
        _upsert_delivered_ref_entry(
            cd, _TOPIC_ID,
            delivered_type="lulu-blueprint",
            path=topic_doc,
            profile_id="lulu-blueprint",
        )
        result = _run_start("lulu-spec", tmp_path)
        payload = _assert_start_ok(result)
        assert payload.get("topic_doc") == str(topic_doc.resolve())
        resolved = json.loads(
            (cd / _CYCLE_ID / "lulu-spec" / "revision1" / "resolved-refs.json").read_text(encoding="utf-8")
        )
        assert resolved["norm_constraint_refs"] == []


# ---------------------------------------------------------------------------
# TestReopen
# ---------------------------------------------------------------------------

class TestReopen:
    def test_marks_historical_true(self, tmp_path):
        """Re-open: to_stage Delivered session gets historical: true in frontmatter."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        ws = _make_session(cd, _CYCLE_ID, "lulu-spec", "r1", "Delivered")
        _make_session_state(cd, _CYCLE_ID, "lulu-spec", active=1)
        _make_cycle_state(cd, _CYCLE_ID, "lulu-spec")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)
        assert "historical: true" in ws.read_text(encoding="utf-8")

    def test_old_revision_file_preserved(self, tmp_path):
        """Re-open must NOT delete old revision files."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        ws = _make_session(cd, _CYCLE_ID, "lulu-spec", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-spec")
        _run_start("lulu-spec", tmp_path)
        assert ws.exists(), "Old revision workflow-state.md must still exist"

    def test_invalidates_downstream(self, tmp_path):
        """Re-open: downstream stages are Invalidated."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-spec", "r1", "Delivered")
        downstream_ws = _make_session(cd, _CYCLE_ID, "lulu-approach", "r1", "InProgress")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-spec")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)
        assert "Invalidated" in downstream_ws.read_text(encoding="utf-8")

    def test_creates_new_session_after_reopen(self, tmp_path):
        """Re-open + gate passes → new session is still created."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-spec", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-spec")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)


# ---------------------------------------------------------------------------
# TestBackfill
# ---------------------------------------------------------------------------

class TestBackfill:
    def test_invalidates_later_delivered_stages(self, tmp_path):
        """Back-fill: to_stage < latest Delivered → invalidate_downstream from to_stage."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        # lulu-bet Delivered + cycle-state.json → gate OK for lulu-spec
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        # No lulu-spec session (re-open won't trigger)
        # Later stages Delivered → back-fill fires
        tech_diag_ws = _make_session(cd, _CYCLE_ID, "lulu-approach", "r1", "Delivered")
        tech_plan_ws = _make_session(cd, _CYCLE_ID, "lulu-plan", "r1", "Delivered")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)
        assert "Invalidated" in tech_diag_ws.read_text(encoding="utf-8")
        assert "Invalidated" in tech_plan_ws.read_text(encoding="utf-8")

    def test_no_backfill_when_no_later_delivered(self, tmp_path):
        """No back-fill when no later stages are Delivered."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)


# ---------------------------------------------------------------------------
# TestGetTopicDoc
# ---------------------------------------------------------------------------

class TestGetTopicDoc:
    def test_topic_id_no_topics_json_exits_1(self, tmp_path):
        """Feature has topic_id but cycles.json absent → ValueError → exit 1."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        result = _run_start("lulu-spec", tmp_path)
        _assert_topic_unresolved(result, "lulu-spec")

    def test_topic_id_no_topics_json_no_session(self, tmp_path):
        """ValueError prevents session creation."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _run_start("lulu-spec", tmp_path)
        spec_dir = cd / _CYCLE_ID / "lulu-spec"
        assert not spec_dir.exists() or not any(spec_dir.rglob("workflow-state.md"))

    def test_no_topic_id_session_created(self, tmp_path):
        """No topic_id → get_topic_doc returns None → session created normally."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)

    def test_valid_topic_no_delivered_session_created(self, tmp_path):
        """Valid topic but no Delivered session for it → None → session created."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _make_cycles_json(cd, _TOPIC_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        result = _run_start("lulu-spec", tmp_path)
        _assert_start_ok(result)

    def test_topic_id_not_in_topics_json_exits_1(self, tmp_path):
        """topic_id not in cycles.json → ValueError → exit 1."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _make_cycles_json(cd, "topic-other-000-aabbccdd")
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        result = _run_start("lulu-spec", tmp_path)
        _assert_topic_unresolved(result, "lulu-spec")

    def test_topic_delivered_doc_printed_from_delivered_refs(self, tmp_path):
        """Topic's lulu-blueprint delivered → start JSON reports topic_doc."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _make_cycles_json(cd, _TOPIC_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Delivered")
        _make_cycle_state(cd, _CYCLE_ID, "lulu-bet")
        topic_doc = tmp_path / "topic-product-doc.md"
        topic_doc.write_text("# Topic Product Doc\n", encoding="utf-8")
        _upsert_delivered_ref_entry(
            cd, _TOPIC_ID,
            delivered_type="lulu-blueprint",
            path=topic_doc,
            profile_id="lulu-blueprint",
        )
        result = _run_start("lulu-spec", tmp_path)
        payload = _assert_start_ok(result)
        assert payload.get("topic_doc") == str(topic_doc.resolve())


# ---------------------------------------------------------------------------
# TestAllStagesGateIntegration
# ---------------------------------------------------------------------------

class TestAllStagesGateIntegration:
    """Verify all 5 start.py files carry the gate integration."""

    @pytest.mark.parametrize("stage", _STAGES_WITH_GATE)
    def test_gate_blocked_all_stages(self, stage, tmp_path):
        """Each gated start.py exits 1 when lulu-bet is Drafting."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _make_session(cd, _CYCLE_ID, "lulu-bet", "r1", "Working")
        result = _run_start(stage, tmp_path)
        _assert_gate_blocked(result, stage)

    @pytest.mark.parametrize("stage", _STAGES_VALIDATING_TOPIC_LINKAGE)
    def test_topic_missing_topics_json_all_stages(self, stage, tmp_path):
        """All topic-aware start.py: feature with topic_id + no registered topic cycle → exit 1."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        _all_prior_delivered(cd, _CYCLE_ID, stage)
        result = _run_start(stage, tmp_path)
        _assert_topic_unresolved(result, stage)

    def test_decision_start_ignores_broken_topic_linkage(self, tmp_path):
        """decision (shared kernel) never calls get_topic_ref itself, so a feature with an
        unregistered topic_id does not block $DEC_START — only the holder's own resolver
        script (or a compose adapter) surfaces that error, never decision."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID, extra={"topic_id": _TOPIC_ID})
        result = _run_start("decision", tmp_path)
        assert result.returncode == 0, result.stderr

    @pytest.mark.parametrize("stage", _STAGES_WITH_GATE)
    def test_reopen_marks_historical_all_stages(self, stage, tmp_path):
        """All gated start.py mark historical when their stage has a prior Delivered session."""
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        old_ws = _make_session(cd, _CYCLE_ID, stage, "r1", "Delivered")
        # Create session-state.md so start.py increments to the next revision
        _make_session_state(cd, _CYCLE_ID, stage, active=1)
        _make_cycle_state(cd, _CYCLE_ID, stage)
        result = _run_start(stage, tmp_path)
        if stage in _COMPOSE_START_STAGES:
            _assert_start_ok(result)
        else:
            assert result.returncode == 0, f"{stage}: {result.stderr}"
        assert "historical: true" in old_ws.read_text(encoding="utf-8"), (
            f"{stage}: expected historical: true in old session"
        )

#!/usr/bin/env python3
"""Tests for t3: start.py --cycle-id + archive call deferral in all 5 stages."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

_SRC = Path(__file__).resolve().parents[3]  # lulu-dev-skills/
_STAGES = ["diagnostic", "product-plan", "tech-plan", "tech-work-order", "tech-code"]
# compose-kernel start.py never integrated run_archive; other stages defer via comment.
_STAGES_WITH_DEFERRED_ARCHIVE = [s for s in _STAGES if s != "tech-plan"]
_FID = "20260524143022-02cd7e6e"
_CONV_ID = "test-conversation-aaa"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}
_FEATURE_CYCLE = [
    "product-diagnostic", "product-plan", "tech-diagnostic",
    "tech-plan", "tech-work-order", "tech-code",
]


def _start_py(stage: str) -> Path:
    if stage == "tech-plan":
        return _SRC / "lulu-dev-workflow" / "compose-kernel" / "scripts" / "core" / "start.py"
    return _SRC / "lulu-dev-workflow" / stage / "scripts" / ({"tech-code": "tc_start.py", "diagnostic": "dx_start.py", "product-plan": "pp_start.py", "tech-work-order": "two_start.py"}.get(stage, "start.py"))


def _scripts_dir(stage: str) -> Path:
    if stage == "tech-plan":
        return _SRC / "lulu-dev-workflow" / "compose-kernel" / "scripts" / "core"
    return _SRC / "lulu-dev-workflow" / stage / "scripts"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def _seed_work_order_handoff(tmp_path: Path, cycle_id: str, active_doc: int = 1) -> None:
    cd = _cache_dir(tmp_path)
    wo_dir = cd / cycle_id / "tech" / "work-order"
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


def _make_cycles_json(cache_dir: Path, cycle_id: str, name: str = "Test Cycle") -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj = cache_dir / "cycles.json"
    data = {}
    if cj.exists():
        import json
        data = json.loads(cj.read_text(encoding="utf-8"))
    data[cycle_id] = {"name": name, "execution_mode": "copilot"}
    import json
    cj.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_cycle_state(cache_dir: Path, cycle_id: str, stage: str) -> None:
    import json
    p = cache_dir / cycle_id / "cycle-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"current_stage": stage, "updated_at": "2026-06-01T00:00:00+00:00"}),
        encoding="utf-8",
    )


def _make_session(cache_dir: Path, cycle_id: str, stage: str, revision: str) -> None:
    scripts_root = _SRC / "lulu-dev-workflow" / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    from workflow_sessions import STAGE_FLAT, stage_subdir  # noqa: E402

    subdir = stage_subdir(stage)
    if stage in STAGE_FLAT:
        session_dir = cache_dir / cycle_id / subdir
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "session-state.md"
    else:
        rev_name = f"revision{revision.lstrip('r')}"
        session_dir = cache_dir / cycle_id / subdir / rev_name
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
    ws.write_text(
        "---\ncurrent_state: Delivered\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _upsert_delivered_ref_entry(
    cache_dir: Path,
    cycle_id: str,
    *,
    delivered_type: str,
    path: Path,
    profile_id: str,
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
    data["entries"] = entries
    refs_path.parent.mkdir(parents=True, exist_ok=True)
    refs_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_tech_plan_delivered_refs(
    cache_dir: Path,
    cycle_id: str,
    project_root: Path,
    *,
    design_path: Optional[Path] = None,
) -> None:
    del project_root
    diag_dir = cache_dir / cycle_id / "tech" / "diagnostic"
    diag_dir.mkdir(parents=True, exist_ok=True)
    decision = diag_dir / "decision-doc.md"
    if not decision.is_file():
        decision.write_text("# Decision\n", encoding="utf-8")
    _upsert_delivered_ref_entry(
        cache_dir,
        cycle_id,
        delivered_type="tech-diagnostic",
        path=decision,
        profile_id="tech-diagnostic",
    )
    if design_path is not None:
        _upsert_delivered_ref_entry(
            cache_dir,
            cycle_id,
            delivered_type="tech-design",
            path=design_path,
            profile_id="tech-design",
        )


def _seed_gate_for_stage(tmp_path: Path, to_stage: str) -> None:
    if to_stage not in _FEATURE_CYCLE:
        return
    cd = _cache_dir(tmp_path)
    _make_cycles_json(cd, _FID)
    idx = _FEATURE_CYCLE.index(to_stage)
    prior = _FEATURE_CYCLE[:idx]
    for stage in prior:
        _make_session(cd, _FID, stage, "r1")
    if prior:
        _make_cycle_state(cd, _FID, prior[-1])
    if to_stage == "tech-plan":
        _seed_tech_plan_delivered_refs(cd, _FID, tmp_path)


# ---------------------------------------------------------------------------
# Source inspection: --cycle-id replaces --conversation-id
# ---------------------------------------------------------------------------

class TestArgparseSource:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_cycle_id_arg_declared(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        assert '"--cycle-id"' in src or "'--cycle-id'" in src, (
            f"{stage}/start.py: --cycle-id not declared in argparse"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_conversation_id_arg_declared(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        assert '"--conversation-id"' in src or "'--conversation-id'" in src, (
            f"{stage}/start.py: --conversation-id not declared in argparse"
        )


# ---------------------------------------------------------------------------
# Source inspection: archive calls commented with # archive: deferred
# ---------------------------------------------------------------------------

class TestArchiveDeferred:
    @pytest.mark.parametrize("stage", _STAGES_WITH_DEFERRED_ARCHIVE)
    def test_archive_deferred_comment_present(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        assert "# archive: deferred" in src, (
            f"{stage}/start.py: '# archive: deferred' comment not found"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_run_archive_call_is_not_active(self, stage):
        src = _start_py(stage).read_text(encoding="utf-8")
        import re
        # Active (not commented out) call to run_archive(
        active_calls = [
            line for line in src.splitlines()
            if re.search(r"run_archive\(", line) and not line.lstrip().startswith("#")
        ]
        assert active_calls == [], (
            f"{stage}/start.py: run_archive() still has active (uncommented) calls: {active_calls}"
        )


# ---------------------------------------------------------------------------
# Subprocess: --cycle-id recognized, --conversation-id rejected
# ---------------------------------------------------------------------------

class TestArgparseBehavior:
    def _run_missing_args(self, stage: str):
        """Run start.py with no args — expect error."""
        return subprocess.run(
            [sys.executable, str(_start_py(stage))],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )

    def _run_with_conv_id(self, stage: str, tmp_path: Path, extra: list = None):
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--conversation-id", _FID,
        ]
        if extra:
            cmd.extend(extra)
        return subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )

    def test_cycle_id_missing_diagnostic_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(_start_py("diagnostic")), "--project-root", "."],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )
        assert result.returncode != 0

    def test_conversation_id_accepted_diagnostic(self, tmp_path):
        result = self._run_with_conv_id(
            "diagnostic",
            tmp_path,
            extra=["--cycle-id", _FID, "--stage", "tech-diagnostic"],
        )
        assert result.returncode == 0, result.stderr

    def test_start_without_conv_id_no_context_write(self, tmp_path):
        _seed_gate_for_stage(tmp_path, "product-plan")
        env = {k: v for k, v in _ENV_COPILOT.items() if k != "LULU_CONVERSATION_ID"}
        result = subprocess.run(
            [sys.executable, str(_start_py("product-plan")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID],
            capture_output=True, text=True, env=env,
            cwd=str(_scripts_dir("product-plan")),
        )
        assert result.returncode == 0, result.stderr
        assert "conversation_id" in result.stderr
        ctx = _cache_dir(tmp_path) / "active-context.json"
        assert not ctx.exists()


# ---------------------------------------------------------------------------
# Subprocess: successful run creates session file at feature-first path
# ---------------------------------------------------------------------------

class TestSessionPath:
    def _run_diagnostic(self, tmp_path):
        return subprocess.run(
            [sys.executable, str(_start_py("diagnostic")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )

    def _run_product(self, tmp_path):
        _seed_gate_for_stage(tmp_path, "product-plan")
        return subprocess.run(
            [sys.executable, str(_start_py("product-plan")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("product-plan")),
        )

    def _run_tech(self, tmp_path):
        _seed_gate_for_stage(tmp_path, "tech-plan")
        return subprocess.run(
            [sys.executable, str(_start_py("tech-plan")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID,
             "--profile", "tech-plan",
             "--run-mode", "tech"],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("tech-plan")),
        )

    def _run_work_order(self, tmp_path):
        _seed_gate_for_stage(tmp_path, "tech-work-order")
        # tech-work-order requires --tech-ref (existing file)
        tech_ref = tmp_path / "tech-doc.md"
        tech_ref.write_text("# Tech Doc\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(_start_py("tech-work-order")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID,
             "--tech-ref", str(tech_ref)],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("tech-work-order")),
        )

    def _run_code(self, tmp_path):
        _seed_gate_for_stage(tmp_path, "tech-code")
        _seed_work_order_handoff(tmp_path, _FID)
        return subprocess.run(
            [sys.executable, str(_start_py("tech-code")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("tech-code")),
        )

    def test_diagnostic_exits_zero(self, tmp_path):
        result = self._run_diagnostic(tmp_path)
        assert result.returncode == 0, result.stderr

    def test_diagnostic_session_file_at_feature_first_path(self, tmp_path):
        self._run_diagnostic(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "diagnostic" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def _run_diagnostic_with_stage(self, tmp_path, stage: str):
        return subprocess.run(
            [sys.executable, str(_start_py("diagnostic")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID,
             "--stage", stage],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )

    def test_product_diagnostic_stage_exits_zero(self, tmp_path):
        result = self._run_diagnostic_with_stage(tmp_path, "product-diagnostic")
        assert result.returncode == 0, result.stderr

    def test_product_diagnostic_stage_writes_nested_path(self, tmp_path):
        self._run_diagnostic_with_stage(tmp_path, "product-diagnostic")
        ss = _cache_dir(tmp_path) / _FID / "product" / "diagnostic" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_tech_diagnostic_stage_writes_nested_path(self, tmp_path):
        self._run_diagnostic_with_stage(tmp_path, "tech-diagnostic")
        ss = _cache_dir(tmp_path) / _FID / "tech" / "diagnostic" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_product_diagnostic_active_context_stage_value(self, tmp_path):
        import json

        result = subprocess.run(
            [sys.executable, str(_start_py("diagnostic")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID,
             "--stage", "product-diagnostic",
             "--conversation-id", _CONV_ID],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("diagnostic")),
        )
        assert result.returncode == 0, result.stderr
        ctx = _cache_dir(tmp_path) / "active-context.json"
        assert ctx.exists(), f"Expected active-context.json at {ctx}"
        data = json.loads(ctx.read_text(encoding="utf-8"))
        assert _CONV_ID in data, f"missing conv key: {data}"
        assert data[_CONV_ID]["stage"] == "product-diagnostic"
        assert data[_CONV_ID]["cycle_id"] == _FID

    def test_start_writes_conv_indexed_context(self, tmp_path):
        import json

        _seed_gate_for_stage(tmp_path, "tech-plan")
        result = subprocess.run(
            [sys.executable, str(_start_py("tech-plan")),
             "--project-root", str(tmp_path),
             "--cycle-id", _FID,
             "--run-mode", "tech",
             "--conversation-id", _CONV_ID],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("tech-plan")),
        )
        assert result.returncode == 0, result.stderr
        ctx = _cache_dir(tmp_path) / "active-context.json"
        data = json.loads(ctx.read_text(encoding="utf-8"))
        assert _CONV_ID in data
        assert data[_CONV_ID]["stage"] == "tech-plan"

    def test_product_session_file_at_feature_first_path(self, tmp_path):
        self._run_product(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "product" / "plan" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_tech_session_file_at_feature_first_path(self, tmp_path):
        self._run_tech(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "tech" / "plan" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_work_order_session_file_at_feature_first_path(self, tmp_path):
        self._run_work_order(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "tech" / "work-order" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_code_session_file_at_feature_first_path(self, tmp_path):
        self._run_code(tmp_path)
        ss = _cache_dir(tmp_path) / _FID / "tech" / "code" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

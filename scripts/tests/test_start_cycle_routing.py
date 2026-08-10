#!/usr/bin/env python3
"""Tests for t4: container-type routing (topic-id vs cycle-id) in all 5 stages."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

_SRC = Path(__file__).resolve().parents[3]  # lulu-dev-skills/
_LDEV = _SRC / "lulu-dev-workflow"
_KERNEL_START = _LDEV / "compose" / "scripts" / "core" / "start.py"
_COMPOSE_START_STAGES = frozenset({"lulu-plan", "lulu-spec", "lulu-arch", "lulu-blueprint"})
_STAGES = ["decision", "lulu-spec", "lulu-plan", "lulu-tasks", "lulu-code"]

# Use lulu-tasks's tt_workflow_common for unit tests of shared functions.
_TWO_SCRIPTS = _SRC / "lulu-dev-workflow" / "lulu-tasks" / "scripts"
if str(_TWO_SCRIPTS) not in sys.path:
    sys.path.append(str(_TWO_SCRIPTS))

_CYCLE_ID = "20260524143022-02cd7e6e"
_TOPIC_ID = "topic-20260524143022-aabbccdd"
_CONV_ID = "test-conv-t4-routing"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}
_FEATURE_CYCLE = [
    "lulu-bet", "lulu-spec", "lulu-approach",
    "lulu-plan", "lulu-tasks", "lulu-code",
]
# Topic cycles end at lulu-arch; lulu-tasks and lulu-code are feature-only.
_TOPIC_CONTAINER_STAGES = ["decision", "lulu-blueprint", "lulu-arch"]
_TOPIC_CYCLE = [
    "lulu-bet", "lulu-blueprint", "lulu-approach", "lulu-arch",
]


def _start_py(stage: str) -> Path:
    if stage in _COMPOSE_START_STAGES:
        return _KERNEL_START
    return _SRC / "lulu-dev-workflow" / stage / "scripts" / ({"lulu-code": "tc_start.py", "decision": "dec_start.py", "lulu-tasks": "tt_start.py"}.get(stage, "start.py"))


def _scripts_dir(stage: str) -> Path:
    if stage in _COMPOSE_START_STAGES:
        return _KERNEL_START.parent
    return _SRC / "lulu-dev-workflow" / stage / "scripts"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def _make_cycles_json(cache_dir: Path, cycle_id: str, name: str = "Test Cycle") -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj = cache_dir / "cycles.json"
    data = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    data[cycle_id] = {"name": name}
    cj.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_cycle_state(cache_dir: Path, cycle_id: str, stage: str) -> None:
    p = cache_dir / cycle_id / "cycle-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"current_stage": stage, "updated_at": "2026-06-01T00:00:00+00:00"}),
        encoding="utf-8",
    )


def _make_session(cache_dir: Path, cycle_id: str, stage: str, revision: str, state: str) -> None:
    workflow_scripts = _SRC / "lulu-dev-workflow" / "scripts"
    if str(workflow_scripts) not in sys.path:
        sys.path.insert(0, str(workflow_scripts))
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
    artifact: Optional[str] = None,
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
                    "version": 1,
                    "status": "package_ready",
                    "main": {"decision_doc_path": "decision-doc.md"},
                    "slices": [],
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
    design_path: Optional[Path] = None,
) -> None:
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
                    "version": 1,
                    "status": "package_ready",
                    "main": {"decision_doc_path": "decision-doc.md"},
                    "slices": [],
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


def _seed_gate_for_stage(cache_dir: Path, cycle_id: str, to_stage: str, project_root: Path) -> None:
    cycle_order = _TOPIC_CYCLE if cycle_id.startswith("topic-") else _FEATURE_CYCLE
    if to_stage not in cycle_order and to_stage != "decision":
        return
    if to_stage == "decision":
        return
    idx = cycle_order.index(to_stage)
    prior = cycle_order[:idx]
    for stage in prior:
        _make_session(cache_dir, cycle_id, stage, "r1", "Delivered")
    if prior:
        _make_cycle_state(cache_dir, cycle_id, prior[-1])
    if to_stage == "lulu-spec":
        _seed_product_spec_delivered_refs(cache_dir, cycle_id, project_root)
    if to_stage == "lulu-plan":
        _seed_tech_plan_delivered_refs(cache_dir, cycle_id, project_root)
    if to_stage == "lulu-arch":
        _seed_tech_plan_delivered_refs(cache_dir, cycle_id, project_root)
    if to_stage == "lulu-blueprint":
        _seed_product_spec_delivered_refs(cache_dir, cycle_id, project_root)


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





_LDEV = _SRC / "lulu-dev-workflow"


def _compose_start_args(profile_id: str, *extra: str) -> list[str]:
    return [
        "--profile",
        profile_id,
        "--profile-path",
        str(_LDEV / profile_id / "compose-profile.json"),
        *extra,
    ]


def _seed_decision_config(tmp_path: Path) -> None:
    """Seed workflow-config + local decision-doc template for dec_start init-session."""
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Comparison\n\nTBD\n\n"
        "## 4. Settled Direction\n\n"
        "### Decision Rationale\n\nTBD\n\n"
        "### Scope\n\n"
        "**Applies to:** TBD\n\n"
        "**Explicitly excludes:** TBD\n\n"
        "### Landing Approach\n\nTBD\n\n"
        "## 5. Assumptions & Risks\n\nTBD\n\n"
        "## 6. Execution Analysis\n\n### 6.1 Acceptance Criteria\n\nTBD\n",
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
    """Return required extra CLI args for each stage."""
    if stage == "decision":
        return _diag_holder_args("lulu-bet")
    if stage == "lulu-spec":
        return _compose_start_args("lulu-spec")
    elif stage == "lulu-blueprint":
        return _compose_start_args("lulu-blueprint")
    elif stage == "lulu-arch":
        return _compose_start_args("lulu-arch")
    elif stage == "lulu-plan":
        return _compose_start_args("lulu-plan")
    elif stage == "lulu-tasks":
        tech_ref = tmp_path / "tech-doc.md"
        tech_ref.write_text("# Tech Doc\n", encoding="utf-8")
        return ["--tech-ref", str(tech_ref)]
    elif stage == "lulu-code":
        cd = _cache_dir(tmp_path)
        _seed_work_order_handoff(cd, _CYCLE_ID)
        _seed_work_order_handoff(cd, _TOPIC_ID)
        return []
    return []


# ---------------------------------------------------------------------------
# Unit: detect_cycle_type
# ---------------------------------------------------------------------------


class TestDetectContainerType:
    def test_cycle_id_returns_feature(self):
        from tt_workflow_common import detect_cycle_type

        assert detect_cycle_type(_CYCLE_ID) == "feature"

    def test_topic_id_returns_topic(self):
        from tt_workflow_common import detect_cycle_type

        assert detect_cycle_type(_TOPIC_ID) == "topic"

    def test_plain_string_returns_feature(self):
        from tt_workflow_common import detect_cycle_type

        assert detect_cycle_type("some-random-id") == "feature"

    def test_topic_prefix_canonical(self):
        from tt_workflow_common import detect_cycle_type

        assert detect_cycle_type("topic-20260101000000-aabbccdd") == "topic"


# ---------------------------------------------------------------------------
# Unit: load_container_meta
# ---------------------------------------------------------------------------


class TestLoadContainerMeta:
    def test_feature_reads_features_json(self, tmp_path):
        from tt_workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        meta = load_container_meta(cd, _CYCLE_ID, "feature")
        assert meta["name"] == "Test Cycle"

    def test_topic_reads_topics_json(self, tmp_path):
        from tt_workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        meta = load_container_meta(cd, _TOPIC_ID, "topic")
        assert meta["name"] == "Test Cycle"

    def test_feature_not_in_features_json_raises(self, tmp_path):
        from tt_workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "other-00000000-aaaabbbb")
        with pytest.raises(ValueError):
            load_container_meta(cd, _CYCLE_ID, "feature")

    def test_feature_no_features_json_returns_empty(self, tmp_path):
        """Backward compat: cycles.json absent → return {} (no error)."""
        from tt_workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        meta = load_container_meta(cd, _CYCLE_ID, "feature")
        assert meta == {}

    def test_topic_absent_topics_json_raises(self, tmp_path):
        from tt_workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError):
            load_container_meta(cd, _TOPIC_ID, "topic")

    def test_topic_not_in_topics_json_raises(self, tmp_path):
        from tt_workflow_common import load_container_meta

        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "topic-other-000-aaaabbbb")
        with pytest.raises(ValueError):
            load_container_meta(cd, _TOPIC_ID, "topic")


# ---------------------------------------------------------------------------
# active-context.json gets cycle_type field
# ---------------------------------------------------------------------------


class TestActiveContextContainerType:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_cycle_id_writes_cycle_type_feature(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _CYCLE_ID)
        _seed_gate_for_stage(cd, _CYCLE_ID, stage, tmp_path)
        if stage == "decision":
            _seed_decision_config(tmp_path)
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _CYCLE_ID,
            "--conversation-id", _CONV_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode == 0, result.stderr
        ctx = cd / "active-context.json"
        assert ctx.exists(), f"active-context.json not found at {ctx}"
        data = json.loads(ctx.read_text(encoding="utf-8"))
        assert _CONV_ID in data, f"conv key missing: {list(data)}"
        assert data[_CONV_ID]["cycle_type"] == "feature"

    @pytest.mark.parametrize("stage", _TOPIC_CONTAINER_STAGES)
    def test_topic_id_writes_cycle_type_topic(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        _seed_gate_for_stage(cd, _TOPIC_ID, stage, tmp_path)
        if stage == "decision":
            _seed_decision_config(tmp_path)
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _TOPIC_ID,
            "--conversation-id", _CONV_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode == 0, result.stderr
        ctx = cd / "active-context.json"
        assert ctx.exists()
        data = json.loads(ctx.read_text(encoding="utf-8"))
        assert _CONV_ID in data
        assert data[_CONV_ID]["cycle_type"] == "topic"


# ---------------------------------------------------------------------------
# Session path for topic-id is symmetric with cycle-id
# ---------------------------------------------------------------------------


class TestTopicIdSessionPath:
    def test_decision_topic_session_uses_topic_dir(self, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        _seed_decision_config(tmp_path)
        result = subprocess.run(
            [
                sys.executable, str(_start_py("decision")),
                "--project-root", str(tmp_path),
                "--cycle-id", _TOPIC_ID,
            ],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("decision")),
        )
        assert result.returncode == 0, result.stderr
        ss = cd / _TOPIC_ID / "decision" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"

    def test_product_arch_topic_session_uses_topic_dir(self, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, _TOPIC_ID)
        _seed_gate_for_stage(cd, _TOPIC_ID, "lulu-blueprint", tmp_path)
        result = subprocess.run(
            [
                sys.executable, str(_start_py("lulu-blueprint")),
                "--project-root", str(tmp_path),
                "--cycle-id", _TOPIC_ID,
            ] + _compose_start_args("lulu-blueprint"),
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("lulu-blueprint")),
        )
        assert result.returncode == 0, result.stderr
        ss = cd / _TOPIC_ID / "lulu-blueprint" / "session-state.md"
        assert ss.exists(), f"Expected session-state.md at {ss}"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestContainerRoutingErrors:
    @pytest.mark.parametrize("stage", _STAGES)
    def test_cycle_id_not_in_features_json_exits_nonzero(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "other-00000000-aaaabbbb")
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _CYCLE_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode != 0, (
            f"{stage}: expected nonzero exit when cycle_id not in cycles.json"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_topic_id_without_topics_json_exits_nonzero(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _TOPIC_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode != 0, (
            f"{stage}: expected nonzero exit when cycles.json absent"
        )

    @pytest.mark.parametrize("stage", _STAGES)
    def test_topic_id_not_in_topics_json_exits_nonzero(self, stage, tmp_path):
        cd = _cache_dir(tmp_path)
        _make_cycles_json(cd, "topic-other-000-aaaabbbb")
        extra = _stage_extra_args(stage, tmp_path)
        cmd = [
            sys.executable, str(_start_py(stage)),
            "--project-root", str(tmp_path),
            "--cycle-id", _TOPIC_ID,
        ] + extra
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir(stage)),
        )
        assert result.returncode != 0, (
            f"{stage}: expected nonzero exit when topic_id not in cycles.json"
        )


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------


class TestActiveContextBackwardCompat:
    def test_read_entry_without_cycle_type_defaults_to_feature(self, tmp_path):
        """read_all on old-style entries (no cycle_type) must normalize to 'feature'."""
        _scripts = _SRC / "lulu-dev-workflow" / "scripts"
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from active_context_schema import read_all  # noqa: E402

        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        ctx_path = cd / "active-context.json"
        ctx_path.write_text(
            json.dumps({"old-conv-id": {"cycle_id": _CYCLE_ID, "stage": "decision"}}),
            encoding="utf-8",
        )
        data = read_all(tmp_path, "copilot")
        assert "old-conv-id" in data
        assert data["old-conv-id"]["cycle_type"] == "feature"

    def test_old_features_json_without_topic_id_field_works(self, tmp_path):
        """cycles.json entries without topic_id field: cycle-id routing works fine."""
        cd = _cache_dir(tmp_path)
        cd.mkdir(parents=True, exist_ok=True)
        fj = cd / "cycles.json"
        fj.write_text(
            json.dumps({_CYCLE_ID: {"name": "Old Feature"}}),
            encoding="utf-8",
        )
        _seed_decision_config(tmp_path)
        result = subprocess.run(
            [
                sys.executable, str(_start_py("decision")),
                "--project-root", str(tmp_path),
                "--cycle-id", _CYCLE_ID,
                "--conversation-id", _CONV_ID,
            ],
            capture_output=True, text=True, env=_ENV_COPILOT,
            cwd=str(_scripts_dir("decision")),
        )
        assert result.returncode == 0, result.stderr

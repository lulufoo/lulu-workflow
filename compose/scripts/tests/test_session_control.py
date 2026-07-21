#!/usr/bin/env python3
"""Tests for session_control.py."""

import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402
from workflow_paths import EVAL_SCRIPTS, WORKFLOW_SCRIPTS  # noqa: E402

sys.path.insert(0, str(EVAL_SCRIPTS))
_TECH_PLAN_EVAL = (
    Path(__file__).resolve().parents[3] / "lulu-plan" / "scripts" / "eval"
)
if str(_TECH_PLAN_EVAL) not in sys.path:
    sys.path.insert(0, str(_TECH_PLAN_EVAL))
from tech_plan_eval_adapter import TechPlanEvalAdapter  # noqa: E402
from evaluate_state_ops import (  # noqa: E402
    dimension_status_legacy_map,
    init_evaluate_state_for_corpus,
    merge_current_dimension,
)
from evaluate_state_schema import load_evaluate_state, save_evaluate_state  # noqa: E402
import session_control  # noqa: E402
from session_control import (  # noqa: E402
    _CMD_ABANDON,
    _CMD_DELIVER,
    _CMD_READY,
    _CMD_START_EVALUATING,
    abandon_evaluation,
    deliver,
    ready_for_delivery,
    start_evaluating,
)
from workflow_state_schema import init_drafting, load_workflow_state, save_workflow_state
from workflow_paths import (  # noqa: E402
    DEFAULT_COMPOSE_PROFILE_ID,
    load_profile,
    seed_profile_pointer_for_tests,
)
from delivered_refs_schema import load_delivered_refs_file  # noqa: E402

_CYCLE = "feat-test"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_ADAPTER = TechPlanEvalAdapter()


def _corpus(tmp_path: Path):
    return _ADAPTER.resolve_eval_corpus(_CYCLE, tmp_path)


def init_evaluate_state(path: Path, *, tmp_path: Path) -> None:
    init_evaluate_state_for_corpus(
        path,
        _corpus(tmp_path),
        cycle_type="feature",
    )


def _dim_map(es: dict, tmp_path: Path) -> dict[str, str]:
    return dimension_status_legacy_map(es, corpus=_corpus(tmp_path))


def _seed_session(tmp_path: Path, active_doc: int = 1) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, DEFAULT_COMPOSE_PROFILE_ID)
    base = tmp_path / _CACHE / _CYCLE / "lulu-plan"
    base.mkdir(parents=True, exist_ok=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws = base / f"revision{active_doc}" / "workflow-state.md"
    return ws


def _setup_abandon_ready(
    tmp_path: Path,
    *,
    mode: str = "product",
    evaluate_round: int = 1,
    upstream_baseline_ref: str = "/p.md",
    carry_forward_ref: str = "/old.md",
) -> tuple[Path, Path]:
    del upstream_baseline_ref
    ws = _seed_session(tmp_path)
    init_drafting(
        ws,
        mode=mode,
        carry_forward_ref=carry_forward_ref,
        evaluate_round=max(evaluate_round - 1, 0),
    )
    save_workflow_state(
        ws,
        {
            "current_state": "Evaluating",
            "evaluate_round": str(evaluate_round),
            "skip_evaluate_requested": "true",
        },
    )
    es_path = ws.parent / "evaluate-state.md"
    init_evaluate_state(es_path, tmp_path=tmp_path)
    save_evaluate_state(es_path, {"eval_status": "abandoned"})
    return ws, es_path


class TestStartEvaluating:
    def test_from_drafting_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product")

        result = _ADAPTER.enter_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "Evaluating"
        assert result["evaluate_round"] == 1
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Evaluating"
        assert loaded["evaluate_round"] == "1"
        assert "skip_evaluate_requested" not in loaded
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = _dim_map(es, tmp_path)
        assert dim_map["e2"] == "pending"
        assert dim_map["e3"] == "pending"

    def test_from_drafting_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = _ADAPTER.enter_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = _dim_map(es, tmp_path)
        assert "e1" not in dim_map
        assert dim_map["e2"] == "pending"

    def test_increments_evaluate_round(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech", evaluate_round=1)
        save_workflow_state(ws, {"current_state": "Drafting", "evaluate_round": "1"})
        result = _ADAPTER.enter_evaluating(_CYCLE, tmp_path)
        assert result["evaluate_round"] == 2
        loaded = load_workflow_state(ws)
        assert loaded["evaluate_round"] == "2"

    def test_start_evaluating_state_only(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = start_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "Evaluating"
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Evaluating"
        assert not (ws.parent / "evaluate-state.md").exists()

    def test_idempotent_when_already_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        _ADAPTER.enter_evaluating(_CYCLE, tmp_path)
        es_path = ws.parent / "evaluate-state.md"
        es = load_evaluate_state(es_path)
        es = merge_current_dimension(es, "e2", "in_progress", corpus=_corpus(tmp_path))
        save_evaluate_state(es_path, es)
        result = start_evaluating(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["evaluate_round"] == 1
        reloaded = load_evaluate_state(es_path)
        dim_map = _dim_map(reloaded, tmp_path)
        assert dim_map["e2"] == "in_progress"

    def test_failure_from_ready_for_delivery(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        ready_for_delivery(_CYCLE, tmp_path)
        result = start_evaluating(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert result["current_state"] == "ReadyForDelivery"


class TestReadyForDelivery:
    def test_from_drafting_sets_skip_flag(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product")

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "ReadyForDelivery"
        loaded = load_workflow_state(ws)
        assert loaded["skip_evaluate_requested"] == "true"

    def test_from_evaluating_omits_skip_flag(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        save_workflow_state(ws, {"current_state": "Evaluating", "evaluate_round": "1"})

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is True
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "ReadyForDelivery"
        assert "skip_evaluate_requested" not in loaded

    def test_idempotent_when_already_ready(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        ready_for_delivery(_CYCLE, tmp_path)
        result = ready_for_delivery(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_state"] == "ReadyForDelivery"

    def test_failure_from_delivered(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        ready_for_delivery(_CYCLE, tmp_path)
        deliver(_CYCLE, tmp_path)

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["resume"]["entry"] == "Delivered"
        assert "ready-for-delivery" in result["resume"]["action"]


class TestDeliver:
    def test_success_from_ready_for_delivery(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product")
        (ws.parent / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        ready_for_delivery(_CYCLE, tmp_path)

        result = deliver(_CYCLE, tmp_path, note="confirmed")

        assert result["ok"] is True
        assert result["current_state"] == "Delivered"
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Delivered"
        assert "skip_evaluate_requested" not in loaded
        gate = ws.parent / "human-delivery-gate.md"
        assert gate.exists()
        assert "confirmed" in gate.read_text(encoding="utf-8")
        refs = load_delivered_refs_file(_CYCLE, tmp_path)
        assert refs["entries"]["lulu-plan"]["path"] == str((ws.parent / "tech-doc.md").resolve())
        assert "lulu-design-facts" not in refs["entries"]
        assert "lulu-plan-facts" not in refs["entries"]

    def test_deliver_blocked_by_open_agenda_blocker(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product")
        (ws.parent / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        ready_for_delivery(_CYCLE, tmp_path)
        (ws.parent / "agenda.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "items": [
                        {
                            "id": "A-1",
                            "class": "blocker",
                            "status": "open",
                            "text": "两类翻译清单",
                            "async": False,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        result = deliver(_CYCLE, tmp_path, note="should fail")

        assert result["ok"] is False
        assert result["command"] == _CMD_DELIVER
        assert result["current_state"] == "ReadyForDelivery"
        assert "A-1" in result["message"]
        assert load_workflow_state(ws)["current_state"] == "ReadyForDelivery"

    def test_deliver_succeeds_after_ready_then_agenda_cleared(self, tmp_path: Path):
        """Regression: ready then add blocker must still fail; clear → deliver ok."""
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product")
        (ws.parent / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        ready_for_delivery(_CYCLE, tmp_path)
        (ws.parent / "agenda.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "items": [
                        {
                            "id": "A-1",
                            "class": "blocker",
                            "status": "open",
                            "text": "late blocker",
                            "async": False,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        blocked = deliver(_CYCLE, tmp_path)
        assert blocked["ok"] is False

        (ws.parent / "agenda.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "items": [
                        {
                            "id": "A-1",
                            "class": "blocker",
                            "status": "released",
                            "text": "late blocker",
                            "async": False,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        result = deliver(_CYCLE, tmp_path, note="cleared")
        assert result["ok"] is True
        assert result["current_state"] == "Delivered"

    def test_design_deliver_registers_facts_when_present(self, tmp_path: Path):
        seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-design")
        base = tmp_path / _CACHE / _CYCLE / "lulu-design"
        base.mkdir(parents=True, exist_ok=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        ws = base / "revision1" / "workflow-state.md"
        init_drafting(ws, mode="tech")
        (ws.parent / "design-doc.md").write_text("# Design\n", encoding="utf-8")
        (ws.parent / "_facts.json").write_text("[]\n", encoding="utf-8")
        ready_for_delivery(_CYCLE, tmp_path, profile_id="lulu-design")

        result = deliver(_CYCLE, tmp_path, note="design ok", profile_id="lulu-design")

        assert result["ok"] is True
        refs = load_delivered_refs_file(_CYCLE, tmp_path)
        assert refs["entries"]["lulu-design"]["path"] == str(
            (ws.parent / "design-doc.md").resolve()
        )
        assert refs["entries"]["lulu-design"]["facts_path"] == str(
            (ws.parent / "_facts.json").resolve()
        )
        assert "lulu-design-facts" not in refs["entries"]

    def test_design_deliver_skips_facts_when_missing(self, tmp_path: Path):
        seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-design")
        base = tmp_path / _CACHE / _CYCLE / "lulu-design"
        base.mkdir(parents=True, exist_ok=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        ws = base / "revision1" / "workflow-state.md"
        init_drafting(ws, mode="tech")
        (ws.parent / "design-doc.md").write_text("# Design\n", encoding="utf-8")
        ready_for_delivery(_CYCLE, tmp_path, profile_id="lulu-design")

        result = deliver(_CYCLE, tmp_path, profile_id="lulu-design")

        assert result["ok"] is True
        refs = load_delivered_refs_file(_CYCLE, tmp_path)
        assert "lulu-design" in refs["entries"]
        assert "facts_path" not in refs["entries"]["lulu-design"]
        assert "lulu-design-facts" not in refs["entries"]

    def test_plan_deliver_with_local_facts_does_not_register_facts(
        self, tmp_path: Path
    ):
        """Gate: plan has no deliver_facts; local _facts.json must not be registered."""
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product")
        (ws.parent / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        (ws.parent / "_facts.json").write_text("[]\n", encoding="utf-8")
        ready_for_delivery(_CYCLE, tmp_path)

        result = deliver(_CYCLE, tmp_path, note="plan with facts")

        assert result["ok"] is True
        refs = load_delivered_refs_file(_CYCLE, tmp_path)
        assert "lulu-plan" in refs["entries"]
        assert "lulu-design-facts" not in refs["entries"]
        assert "lulu-plan-facts" not in refs["entries"]

    def test_design_deliver_skips_facts_when_deliver_facts_false(
        self, tmp_path: Path, monkeypatch
    ):
        """Explicit deliver_facts=false skips registration even when _facts.json exists."""

        def _load_profile_no_facts(profile_id: str, **kwargs):
            data = dict(load_profile(profile_id, **kwargs))
            if profile_id == "lulu-design":
                di = dict(data.get("delivery_index") or {})
                di["deliver_facts"] = False
                data["delivery_index"] = di
            return data

        monkeypatch.setattr(session_control, "load_profile", _load_profile_no_facts)
        seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-design")
        base = tmp_path / _CACHE / _CYCLE / "lulu-design"
        base.mkdir(parents=True, exist_ok=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        ws = base / "revision1" / "workflow-state.md"
        init_drafting(ws, mode="tech")
        (ws.parent / "design-doc.md").write_text("# Design\n", encoding="utf-8")
        (ws.parent / "_facts.json").write_text("[]\n", encoding="utf-8")
        ready_for_delivery(_CYCLE, tmp_path, profile_id="lulu-design")

        result = deliver(_CYCLE, tmp_path, profile_id="lulu-design")

        assert result["ok"] is True
        refs = load_delivered_refs_file(_CYCLE, tmp_path)
        assert "lulu-design" in refs["entries"]
        assert "facts_path" not in refs["entries"]["lulu-design"]
        assert "lulu-design-facts" not in refs["entries"]

    def test_failure_from_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        save_workflow_state(ws, {"current_state": "Evaluating"})

        result = deliver(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["current_state"] == "Evaluating"
        assert result["message"] == (
            "deliver 被拒绝：当前状态为 Evaluating，"
            "预期状态为 ReadyForDelivery。请暂停执行，等待用户指示。"
        )
        assert "resume" not in result

    def test_failure_from_drafting(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = deliver(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert "Drafting" in result["message"]
        assert "resume" not in result


class TestAbandonEvaluation:
    def test_success_from_evaluating_abandoned(self, tmp_path: Path):
        ws, _ = _setup_abandon_ready(tmp_path, evaluate_round=2)

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["command"] == _CMD_ABANDON
        assert result["current_state"] == "Drafting"
        assert result["evaluate_round"] == 2
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Drafting"
        assert loaded["evaluate_round"] == "2"
        assert loaded["skip_evaluate_requested"] == "false"
        assert loaded["mode"] == "product"
        assert loaded["carry_forward_ref"] == "/old.md"

    def test_failure_when_not_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["command"] == _CMD_ABANDON
        assert result["current_state"] == "Drafting"
        assert "Evaluating" in result["message"]
        assert "resume" not in result

    def test_failure_when_not_abandoned(self, tmp_path: Path):
        ws, es_path = _setup_abandon_ready(tmp_path, mode="tech")
        save_evaluate_state(es_path, {"eval_status": "active"})

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["current_state"] == "Evaluating"
        assert "abandoned" in result["message"]
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Evaluating"

    def test_failure_when_evaluate_state_missing(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        save_workflow_state(ws, {"current_state": "Evaluating", "evaluate_round": "1"})

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert "evaluate-state.md" in result["message"]
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Evaluating"


class TestCli:
    def test_start_evaluating_json_on_stdout(self, tmp_path: Path):
        import subprocess

        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        script = CORE / "session_control.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                _CMD_START_EVALUATING,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True
        assert payload["command"] == _CMD_START_EVALUATING
        assert payload["evaluate_round"] == 1

    def test_abandon_evaluation_json_on_stdout(self, tmp_path: Path):
        import subprocess

        _setup_abandon_ready(tmp_path, mode="tech", evaluate_round=1)
        script = CORE / "session_control.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                _CMD_ABANDON,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True
        assert payload["command"] == _CMD_ABANDON
        assert payload["current_state"] == "Drafting"

    def test_deliver_failure_json_on_stdout(self, tmp_path: Path):
        import subprocess

        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        script = CORE / "session_control.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                _CMD_DELIVER,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False
        assert payload["command"] == _CMD_DELIVER
        assert "message" in payload
        assert "resume" not in payload
        assert "ReadyForDelivery" in payload["message"]

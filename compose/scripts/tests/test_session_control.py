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
from workflow_state_schema import init_compose_session, load_workflow_state, save_workflow_state
from workflow_paths import (  # noqa: E402
    DEFAULT_COMPOSE_PROFILE_ID,
    seed_profile_pointer_for_tests,
)
from delivered_refs_schema import load_delivered_refs_file  # noqa: E402
from init_working_helpers import (  # noqa: E402
    init_working_ready,
    lock_single_l1_tree,
    mark_all_l_accepted,
    mark_focus_evaluating,
    mark_focus_intake_done,
)
from session_control import split_complete  # noqa: E402

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
    init_working_ready(
        ws,
        mode=mode,
        carry_forward_ref=carry_forward_ref,
        evaluate_round=max(evaluate_round - 1, 0),
    )
    save_workflow_state(
        ws,
        {
            "current_state": "Working",
            "evaluate_round": str(evaluate_round),
        },
    )
    mark_focus_evaluating(ws.parent)
    es_path = ws.parent / "evaluate-state.md"
    init_evaluate_state(es_path, tmp_path=tmp_path)
    save_evaluate_state(es_path, {"eval_status": "abandoned"})
    return ws, es_path


class TestStartEvaluating:
    def test_from_working_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")
        mark_focus_intake_done(ws.parent)

        result = _ADAPTER.enter_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "Working"
        assert result["phase"] == "evaluating"
        assert result["evaluate_round"] == 1
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Working"
        # Per-L rounds live on evaluate-state.md; revision-global stays put.
        assert loaded["evaluate_round"] == "0"
        assert "skip_evaluate_requested" not in loaded
        es = load_evaluate_state(ws.parent / "L1" / "evaluate-state.md")
        assert es.get("evaluate_round") == "1"
        assert es.get("focus_l") == "L1"
        dim_map = _dim_map(es, tmp_path)
        assert dim_map["e2"] == "pending"
        assert dim_map["e3"] == "pending"

    def test_from_working_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_focus_intake_done(ws.parent)

        result = _ADAPTER.enter_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "Working"
        es = load_evaluate_state(ws.parent / "L1" / "evaluate-state.md")
        dim_map = _dim_map(es, tmp_path)
        assert "e1" not in dim_map
        assert dim_map["e2"] == "pending"

    def test_increments_per_l_evaluate_round_after_done(self, tmp_path: Path):
        from discussion_pointer_schema import (  # noqa: WPS433
            load_discussion_pointer,
            save_discussion_pointer,
        )
        from dependency_tree_schema import load_dependency_tree  # noqa: WPS433

        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_focus_intake_done(ws.parent)
        first = _ADAPTER.enter_evaluating(_CYCLE, tmp_path)
        assert first["evaluate_round"] == 1
        es_path = ws.parent / "L1" / "evaluate-state.md"
        save_evaluate_state(es_path, {"eval_status": "done", "evaluate_round": "1"})
        pointer = load_discussion_pointer(ws.parent)
        pointer["by_id"][pointer["focus"]]["phase"] = "in_progress"
        save_discussion_pointer(
            ws.parent, pointer, tree=load_dependency_tree(ws.parent)
        )
        second = _ADAPTER.enter_evaluating(_CYCLE, tmp_path)
        assert second["evaluate_round"] == 2
        reloaded = load_evaluate_state(es_path)
        assert reloaded.get("evaluate_round") == "2"
        # Revision-global counter remains unused for per-L layout.
        assert load_workflow_state(ws)["evaluate_round"] == "0"

    def test_start_evaluating_state_only(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_focus_intake_done(ws.parent)

        result = start_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "Working"
        assert result["phase"] == "evaluating"
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Working"
        assert not (ws.parent / "evaluate-state.md").exists()

    def test_idempotent_when_already_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_focus_intake_done(ws.parent)
        _ADAPTER.enter_evaluating(_CYCLE, tmp_path)
        es_path = ws.parent / "L1" / "evaluate-state.md"
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
        init_working_ready(ws, mode="tech")
        mark_all_l_accepted(ws.parent)
        ready_for_delivery(_CYCLE, tmp_path)
        result = start_evaluating(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert result["current_state"] == "ReadyForDelivery"


class TestReadyForDelivery:
    def test_rejects_without_all_accepted(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert "not all L accepted" in result["error"]
        assert load_workflow_state(ws)["current_state"] == "Working"

    def test_from_working_when_all_accepted(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_all_l_accepted(ws.parent)

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is True
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "ReadyForDelivery"
        assert "skip_evaluate_requested" not in loaded

    def test_idempotent_when_already_ready(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_all_l_accepted(ws.parent)
        ready_for_delivery(_CYCLE, tmp_path)
        result = ready_for_delivery(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_state"] == "ReadyForDelivery"

    def test_failure_from_delivered(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        (ws.parent / "L1" / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        mark_all_l_accepted(ws.parent)
        ready_for_delivery(_CYCLE, tmp_path)
        delivered = deliver(_CYCLE, tmp_path)
        assert delivered["ok"] is True

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["resume"]["entry"] == "Delivered"
        assert "ready-for-delivery" in result["resume"]["action"]


class TestDeliver:
    def test_success_from_ready_for_delivery(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")
        (ws.parent / "L1" / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        mark_all_l_accepted(ws.parent)
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
        assert refs["entries"]["lulu-plan"]["path"] == str(
            (ws.parent / "tech-package.json").resolve()
        )
        assert (ws.parent / "tech-package.json").is_file()
        assert "lulu-design-facts" not in refs["entries"]
        assert "lulu-plan-facts" not in refs["entries"]

    def test_deliver_blocked_by_open_agenda_blocker(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")
        (ws.parent / "L1" / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        mark_all_l_accepted(ws.parent)
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
        init_working_ready(ws, mode="product")
        (ws.parent / "L1" / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        mark_all_l_accepted(ws.parent)
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

    def test_design_deliver_does_not_register_facts_when_present(self, tmp_path: Path):
        """Local _facts.json is never registered on deliver (delivery SSOT = doc)."""
        seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-design")
        base = tmp_path / _CACHE / _CYCLE / "lulu-design"
        base.mkdir(parents=True, exist_ok=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        ws = base / "revision1" / "workflow-state.md"
        init_working_ready(ws, mode="tech")
        (ws.parent / "L1" / "design-doc.md").write_text("# Design\n", encoding="utf-8")
        (ws.parent / "_facts.json").write_text("[]\n", encoding="utf-8")
        mark_all_l_accepted(ws.parent)
        ready_for_delivery(_CYCLE, tmp_path, profile_id="lulu-design")

        result = deliver(_CYCLE, tmp_path, note="design ok", profile_id="lulu-design")

        assert result["ok"] is True
        refs = load_delivered_refs_file(_CYCLE, tmp_path)
        assert refs["entries"]["lulu-design"]["path"] == str(
            (ws.parent / "design-package.json").resolve()
        )
        assert (ws.parent / "design-package.json").is_file()
        assert "facts_path" not in refs["entries"]["lulu-design"]
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
        init_working_ready(ws, mode="tech")
        (ws.parent / "L1" / "design-doc.md").write_text("# Design\n", encoding="utf-8")
        mark_all_l_accepted(ws.parent)
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
        """Plan local _facts.json must not be registered on deliver."""
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")
        (ws.parent / "L1" / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
        (ws.parent / "_facts.json").write_text("[]\n", encoding="utf-8")
        mark_all_l_accepted(ws.parent)
        ready_for_delivery(_CYCLE, tmp_path)

        result = deliver(_CYCLE, tmp_path, note="plan with facts")

        assert result["ok"] is True
        refs = load_delivered_refs_file(_CYCLE, tmp_path)
        assert "lulu-plan" in refs["entries"]
        assert "facts_path" not in refs["entries"]["lulu-plan"]
        assert "lulu-design-facts" not in refs["entries"]
        assert "lulu-plan-facts" not in refs["entries"]

    def test_failure_from_working(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")

        result = deliver(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["current_state"] == "Working"
        assert "Working" in result["message"]
        assert "ReadyForDelivery" in result["message"]
        assert "resume" not in result


class TestAbandonEvaluation:
    def test_success_from_evaluating_abandoned(self, tmp_path: Path):
        ws, _ = _setup_abandon_ready(tmp_path, evaluate_round=2)

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["command"] == _CMD_ABANDON
        assert result["current_state"] == "Working"
        assert result["evaluate_round"] == 2
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Working"
        assert loaded["evaluate_round"] == "2"
        assert "skip_evaluate_requested" not in loaded
        assert loaded["mode"] == "product"
        assert loaded["carry_forward_ref"] == "/old.md"

    def test_failure_when_not_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["command"] == _CMD_ABANDON
        assert result["current_state"] == "Working"
        assert "abandoned" in result["message"] or "evaluate-state" in result["message"]
        assert "resume" not in result

    def test_failure_when_not_abandoned(self, tmp_path: Path):
        ws, es_path = _setup_abandon_ready(tmp_path, mode="tech")
        save_evaluate_state(es_path, {"eval_status": "active"})

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["current_state"] == "Working"
        assert "abandoned" in result["message"]
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Working"

    def test_failure_when_evaluate_state_missing(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        save_workflow_state(ws, {"current_state": "Working", "evaluate_round": "1"})
        mark_focus_evaluating(ws.parent)

        result = abandon_evaluation(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert "evaluate-state.md" in result["message"]
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Working"


class TestCli:
    def test_start_evaluating_json_on_stdout(self, tmp_path: Path):
        import subprocess

        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_focus_intake_done(ws.parent)
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
        assert payload["current_state"] == "Working"

    def test_deliver_failure_json_on_stdout(self, tmp_path: Path):
        import subprocess

        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
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


class TestSplitComplete:
    def test_split_to_working_with_locked_l1(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_compose_session(ws, mode="tech")
        assert load_workflow_state(ws)["current_state"] == "Split"
        lock_single_l1_tree(ws.parent)

        result = split_complete(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "Working"
        assert result.get("transitioned") is True
        assert load_workflow_state(ws)["current_state"] == "Working"

    def test_split_complete_rejects_without_tree(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_compose_session(ws, mode="tech")

        result = split_complete(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["current_state"] == "Split"
        assert "dependency tree" in (result.get("error") or "").lower() or (
            "tree" in (result.get("resume") or {}).get("action", "").lower()
        )

    def test_start_evaluating_rejects_without_topology(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_compose_session(ws, mode="tech")
        save_workflow_state(ws, {"current_state": "Working"})

        result = start_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["current_state"] == "Working"

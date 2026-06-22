#!/usr/bin/env python3
"""Tests for tech_plan_draft_control.py."""

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_DRAFTING = _SCRIPTS_ROOT / "drafting"
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts" / "tests"
if str(_KERNEL_TESTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_TESTS))
if str(_DRAFTING) not in sys.path:
    sys.path.insert(0, str(_DRAFTING))
import bootstrap  # noqa: F401
from tech_plan_draft_control import (  # noqa: E402
    advance_round,
    advance_to_freeedit,
    begin_init,
    begin_round,
    draft_status,
    init_complete,
)

from test_template_data import LEGACY_SECTION_REGISTRY, seed_template_cache  # noqa: E402
from test_registry_fixtures import (  # noqa: E402
    first_section_key,
    minimal_compose_doc_markdown,
)

_CYCLE = "feat-draft-control"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_SCRIPT = _DRAFTING / "tech_plan_draft_control.py"


def _seed_registry_cache(tmp_path: Path) -> None:
    seed_template_cache(tmp_path, "tech-plan", "tpt_section_registry_url", LEGACY_SECTION_REGISTRY)


def _seed_session(tmp_path: Path, *, active_doc: int = 1) -> Path:
    _seed_registry_cache(tmp_path)
    base = tmp_path / _CACHE / _CYCLE / "tech" / "plan"
    revision = base / f"revision{active_doc}"
    revision.mkdir(parents=True, exist_ok=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\n---\n",
        encoding="utf-8",
    )
    diag_dir = tmp_path / _CACHE / _CYCLE / "tech" / "diagnostic"
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
    return revision


def _write_compose_doc(revision: Path) -> None:
    (revision / "tech-doc.md").write_text(minimal_compose_doc_markdown(), encoding="utf-8")


class TestBeginInit:
    def test_absent_progress_ok(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        result = begin_init(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] is None
        assert "dispatch_input" in result
        assert f"REVISION_DIR:         {(revision).resolve().as_posix()}" in result["dispatch_input"]
        assert f"CYCLE_ID:             {_CYCLE}" in result["dispatch_input"]
        assert "CYCLE_TYPE:           feature" in result["dispatch_input"]
        assert "tech/diagnostic/decision-doc.md" in result["dispatch_input"]

    def test_ready_ok(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        (revision / "drafting-progress.md").write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE}\ncurrent_step: Ready\n---\n",
            encoding="utf-8",
        )
        result = begin_init(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "Ready"
        assert "dispatch_input" in result

    def test_round_iteration_blocked(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        (revision / "drafting-progress.md").write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE}\ncurrent_step: RoundIteration\nround: 1\n---\n",
            encoding="utf-8",
        )
        result = begin_init(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "RoundIteration" in result["reason"]
        assert "dispatch_input" not in result


class TestInitComplete:
    def test_writes_ready(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is True
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "current_step: Ready" in progress
        assert f"cycle_id: {_CYCLE}" in progress

    def test_fails_without_compose_doc(self, tmp_path: Path):
        _seed_session(tmp_path)
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "compose document not found" in result["reason"]

    def test_fails_when_section_body_empty(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        (revision / "tech-doc.md").write_text(
            minimal_compose_doc_markdown().replace(f"{first_section_key()}.\n", "\n", 1),
            encoding="utf-8",
        )
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "empty body" in result["reason"]

    def test_fails_when_section_missing_display_title(self, tmp_path: Path):
        from section_registry_schema import section_order  # noqa: WPS433

        revision = _seed_session(tmp_path)
        key = first_section_key()
        lines = ["---\n"]
        for section_key in section_order():
            if section_key == key:
                lines.append(f"\n<!-- section-key:{section_key} -->\n\nBody.\n")
            else:
                lines.append(
                    f"\n### Title for {section_key} <!-- section-key:{section_key} -->\n\n"
                    f"{section_key} body.\n"
                )
        (revision / "tech-doc.md").write_text("".join(lines), encoding="utf-8")
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "missing display title" in result["reason"]

    def test_idempotent_when_already_ready(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        init_complete(_CYCLE, tmp_path)
        result = init_complete(_CYCLE, tmp_path)
        assert result["ok"] is True


class TestBeginRound:
    def test_transitions_ready_to_round_iteration(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        init_complete(_CYCLE, tmp_path)
        result = begin_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "RoundIteration"
        assert result["round"] == 1
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "current_step: RoundIteration" in progress
        assert "round: 1" in progress
        pointer = revision / "round-1" / "section-pointer.json"
        assert pointer.exists()

    def test_idempotent_when_already_round_iteration(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        init_complete(_CYCLE, tmp_path)
        begin_round(_CYCLE, tmp_path)
        result = begin_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["round"] == 1

    def test_fails_without_progress(self, tmp_path: Path):
        _seed_session(tmp_path)
        result = begin_round(_CYCLE, tmp_path)
        assert result["ok"] is False


class TestAdvanceRound:
    def _begin(self, tmp_path: Path) -> Path:
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        init_complete(_CYCLE, tmp_path)
        begin_round(_CYCLE, tmp_path)
        return revision

    def test_increments_round(self, tmp_path: Path):
        revision = self._begin(tmp_path)
        result = advance_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["round"] == 2
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "round: 2" in progress
        assert "current_step: RoundIteration" in progress


class TestAdvanceToFreeedit:
    def test_transitions_to_freeedit(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        init_complete(_CYCLE, tmp_path)
        begin_round(_CYCLE, tmp_path)
        result = advance_to_freeedit(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "FreeEdit"
        progress = (revision / "drafting-progress.md").read_text(encoding="utf-8")
        assert "current_step: FreeEdit" in progress

    def test_idempotent_when_already_freeedit(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        init_complete(_CYCLE, tmp_path)
        begin_round(_CYCLE, tmp_path)
        advance_to_freeedit(_CYCLE, tmp_path)
        result = advance_to_freeedit(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "FreeEdit"


class TestDraftStatus:
    def test_returns_round_and_step(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        _write_compose_doc(revision)
        init_complete(_CYCLE, tmp_path)
        begin_round(_CYCLE, tmp_path)
        result = draft_status(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_step"] == "RoundIteration"
        assert result["round"] == 1
        assert result["cycle_id"] == _CYCLE


class TestCli:
    def test_begin_init_plaintext_stdout(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "begin-init",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert proc.stdout.startswith("REVISION_DIR:")
        assert revision.resolve().as_posix() in proc.stdout
        assert f"CYCLE_ID:             {_CYCLE}" in proc.stdout
        try:
            json.loads(proc.stdout)
            raise AssertionError("expected plain-text stdout, not JSON")
        except json.JSONDecodeError:
            pass

    def test_begin_init_failure_json_stdout(self, tmp_path: Path):
        revision = _seed_session(tmp_path)
        (revision / "drafting-progress.md").write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE}\ncurrent_step: RoundIteration\nround: 1\n---\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "begin-init",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False

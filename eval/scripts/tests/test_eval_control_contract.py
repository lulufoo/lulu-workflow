"""Review-finding regression tests for the Slice 2A Control contract."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import eval_control  # noqa: E402
import evaluate_context  # noqa: E402
import review_binding  # noqa: E402
import session_binding  # noqa: E402
from operation_recovery import (  # noqa: E402
    validate_live_target_digest,
)
from probe_control import (  # noqa: E402
    _render_probe_review,
)
from review_binding import (  # noqa: E402
    canonical_probe_findings_from_reviews,
    validate_review_against_probe_record,
    validate_review_completion,
)
from eval_control import (  # noqa: E402
    build_parser,
    check_dimension,
    complete_probe_only,
    read_b_snapshot_cmd,
    read_unit_view_cmd,
)


def _finding(
    issue_id: str = "q-1",
    *,
    root_cause: str = "WO-ERROR",
    handling_mode: str = "direct",
    status: str = "pending",
) -> dict[str, str]:
    return {
        "id": issue_id,
        "root_cause": root_cause,
        "handling_mode": handling_mode,
        "sot_ref": "—",
        "location": "target.md:1",
        "severity": "medium",
        "evidence": "old",
        "description": "incorrect",
        "status": status,
        "decision": "—" if status == "pending" else "fix",
        "resolution": "" if status == "pending" else "fixed",
    }


def _probe_record(*findings: dict[str, str]) -> dict:
    return {
        "round_token": "round-1",
        "operation_token": "probe-1",
        "dimension_id": "quality",
        "operation_kind": "probe",
        "phase": "committed",
        "canonical_findings": list(findings),
    }


def test_review_must_match_committed_probe_identity_root_cause_and_mode():
    canonical = _finding()
    record = _probe_record(canonical)
    assert validate_review_against_probe_record([dict(canonical)], record) == [
        canonical,
    ]

    for field, replacement in (
        ("id", "other"),
        ("root_cause", "WO-MISS"),
        ("handling_mode", "human-gated"),
    ):
        changed = dict(canonical)
        changed[field] = replacement
        with pytest.raises(ValueError, match=field):
            validate_review_against_probe_record([changed], record)


def test_review_cannot_add_or_drop_probe_findings():
    first = _finding("q-1")
    second = _finding("q-2")
    record = _probe_record(first, second)
    with pytest.raises(ValueError, match="identity"):
        validate_review_against_probe_record([first], record)
    with pytest.raises(ValueError, match="identity"):
        validate_review_against_probe_record(
            [first, second, _finding("q-3")],
            record,
        )


def test_zero_finding_completion_requires_exactly_empty_review():
    assert validate_review_completion(
        rows=[],
        dimension_id="quality",
        remediation_records=[],
        review_digest=hashlib.sha256(b"empty review").hexdigest(),
    ) is True
    with pytest.raises(ValueError, match="committed remediation"):
        validate_review_completion(
            rows=[_finding(status="resolved")],
            dimension_id="quality",
            remediation_records=[],
            review_digest="a" * 64,
        )


def test_resolved_review_requires_committed_operation_and_matching_digest():
    rows = [_finding(status="resolved")]
    record = {
        "dimension_id": "quality",
        "operation_kind": "remediation",
        "phase": "committed",
        "review_after_digest": "b" * 64,
    }
    assert validate_review_completion(
        rows=rows,
        dimension_id="quality",
        remediation_records=[record],
        review_digest="b" * 64,
    ) is True
    with pytest.raises(ValueError, match="review_after_digest"):
        validate_review_completion(
            rows=rows,
            dimension_id="quality",
            remediation_records=[record],
            review_digest="c" * 64,
        )


def test_probe_only_collection_validates_review_before_returning_findings():
    canonical = _finding()
    record = _probe_record(canonical)
    assert canonical_probe_findings_from_reviews(
        {"quality": [dict(canonical)]},
        [record],
        expected_dimensions=["quality"],
    ) == [{**canonical, "dimension": "quality"}]
    changed = dict(canonical, handling_mode="human-gated")
    with pytest.raises(ValueError, match="handling_mode"):
        canonical_probe_findings_from_reviews(
            {"quality": [changed]},
            [record],
            expected_dimensions=["quality"],
        )


def test_live_target_digest_must_still_match_probe_base(tmp_path: Path):
    target = tmp_path / "target.md"
    target.write_text("before", encoding="utf-8")
    expected = hashlib.sha256(target.read_bytes()).hexdigest()
    validate_live_target_digest(target, expected)
    target.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="stale target"):
        validate_live_target_digest(target, expected)


def test_snapshot_commands_accept_operation_token_as_dimension_token_alias():
    parser = build_parser()
    for command in ("read-b-snapshot", "read-evidence-snapshot", "read-unit-view"):
        extra = ["--evidence-ref", "ref"] if command == "read-evidence-snapshot" else []
        via_operation = parser.parse_args(
            ["--cycle-id", "c1", command, "--operation-token", "tok", *extra],
        )
        via_dimension = parser.parse_args(
            ["--cycle-id", "c1", command, "--dimension-token", "tok", *extra],
        )
        assert via_operation.dimension_token == "tok"
        assert via_dimension.dimension_token == "tok"


def test_cli_exposes_only_probe_and_design_section_6_2_commands():
    choices = set(build_parser()._subparsers._group_actions[0].choices)
    expected = {
        "init-round",
        "begin-eval-round",
        "begin-dimension",
        "read-b-snapshot",
        "read-evidence-snapshot",
        "submit-probe-findings",
        "check-dimension",
        "read-unit-view",
        "begin-remediation",
        "begin-dimension-remediation",
        "cancel-remediation",
        "prepare-remediation",
        "apply-remediation",
        "check-dimension-remediation",
        "remediation-complete",
        "complete-probe-only",
    }
    assert choices == expected


def test_read_unit_view_rejects_empty_token(tmp_path: Path):
    result = read_unit_view_cmd("cycle", tmp_path, dimension_token="   ")
    assert result["ok"] is False
    assert result["command"] == "read-unit-view"
    assert "empty" in result["reason"]


def test_read_unit_view_matches_units_and_read_b_snapshot_omits_them(
    tmp_path: Path,
    monkeypatch,
):
    import eval_target_units as etu

    b_text = (
        "# Title\n\n"
        "<!-- chapter:chap-a -->\n"
        "## Alpha\n\n"
        "Prose one.\n"
    )
    snapshot = {"digest": "a" * 64, "content": b_text}
    monkeypatch.setattr(
        evaluate_context,
        "_load_evaluating_context",
        lambda *_: (
            {"current_state": "Working"},
            tmp_path / "workflow.md",
            {"round_token": "round-1"},
            1,
            1,
            "tech",
        ),
    )
    monkeypatch.setattr(
        session_binding,
        "_eval_paths",
        lambda *_, **__: {"evaluate_dir": tmp_path.as_posix()},
    )
    monkeypatch.setattr(
        session_binding,
        "_evaluate_state_path",
        lambda *_: tmp_path / "evaluate-state.md",
    )
    monkeypatch.setattr(
        eval_control,
        "read_target_snapshot",
        lambda **__: snapshot,
    )

    b_result = read_b_snapshot_cmd("cycle", tmp_path, dimension_token="tok")
    view_result = read_unit_view_cmd("cycle", tmp_path, dimension_token="tok")
    expected = etu.units_from_eval_target(b_text)

    assert b_result["ok"] is True
    assert "content" in b_result
    assert "containers" not in b_result
    assert "shape" not in b_result

    assert view_result["ok"] is True
    assert view_result["command"] == "read-unit-view"
    assert "content" not in view_result
    assert view_result["shape"] == expected["shape"]
    assert view_result["containers"] == expected["containers"]
    assert view_result["empty"] == expected["empty"]


def test_probe_commands_forward_to_probe_control():
    import probe_control

    assert probe_control.begin_dimension.__module__ == "probe_control"
    assert eval_control.begin_dimension.__module__ == "eval_control"
    assert probe_control.read_unit_view_cmd.__module__ == "probe_control"


def test_remediation_commands_forward_to_remediation_control():
    import remediation_control

    assert remediation_control.begin_remediation.__module__ == "remediation_control"
    assert eval_control.begin_remediation.__module__ == "eval_control"
    assert remediation_control.apply_remediation.__module__ == "remediation_control"
    assert remediation_control.remediation_complete.__module__ == "remediation_control"


def test_round_commands_forward_to_round_control():
    import round_control

    assert round_control.begin_eval_round.__module__ == "round_control"
    assert eval_control.begin_eval_round.__module__ == "eval_control"
    assert round_control.complete_probe_only.__module__ == "round_control"
    assert round_control.init_round.__module__ == "round_control"


def test_complete_probe_only_validates_before_write_and_replays_idempotently(
    tmp_path: Path,
    monkeypatch,
):
    finding = {
        "id": "q-1",
        "root_cause": "WO-ERROR",
        "handling_mode": "direct",
        "location": "target.md:1",
        "severity": "medium",
        "evidence": "old",
        "description": "incorrect",
    }
    review_path = tmp_path / "quality.md"
    review_path.write_text(
        _render_probe_review(
            dimension_label="Quality",
            dimension_id="quality",
            round_token="round-1",
            active_doc=1,
            evaluate_round=1,
            method_focus="quality",
            handling_policy="class-default",
            findings=[{key: value for key, value in finding.items() if key != "handling_mode"}],
        ),
        encoding="utf-8",
    )
    eval_data = {
        "eval_capability": "probe-only",
        "eval_phase": "probe",
        "eval_status": "active",
        "round_token": "round-1",
        "dimension_status": '{"quality":"probed"}',
    }
    operation = _probe_record(finding)
    commits = 0

    monkeypatch.setattr(
        evaluate_context,
        "_load_evaluating_context",
        lambda *_: (
            {"current_state": "Working"},
            tmp_path / "workflow.md",
            eval_data,
            1,
            1,
            "tech",
        ),
    )
    monkeypatch.setattr(
        session_binding,
        "_eval_paths",
        lambda *_, **__: {
            "evaluate_dir": tmp_path.as_posix(),
            "write_staging_dir": (tmp_path / "staging").as_posix(),
        },
    )
    monkeypatch.setattr(
        session_binding,
        "_evaluate_state_path",
        lambda *_: tmp_path / "evaluate-state.md",
    )
    monkeypatch.setattr(
        session_binding,
        "_operations_for_round",
        lambda *_: [operation],
    )
    monkeypatch.setattr(
        review_binding,
        "_review_path_from_context",
        lambda *_, **__: review_path,
    )
    monkeypatch.setattr(session_binding, "_load_corpus", lambda *_: {})

    def _merge(data, dim, status, *, corpus):
        del dim, corpus
        updated = dict(data)
        updated["dimension_status"] = f'{{"quality":"{status}"}}'
        return updated

    def _commit(*_, update=None, **__):
        nonlocal commits
        commits += 1
        eval_data.update(update(dict(eval_data)))
        return None

    monkeypatch.setattr(eval_control, "merge_current_dimension", _merge)
    monkeypatch.setattr(evaluate_context, "_commit_staged_evaluate_state", _commit)

    first = complete_probe_only("cycle", tmp_path)
    second = complete_probe_only("cycle", tmp_path)

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert commits == 1
    assert second["issues"] == [{**finding, "dimension": "quality"}]


def _patch_check_dimension_context(
    monkeypatch,
    tmp_path: Path,
    *,
    dim_status: str,
    review_path: Path,
) -> None:
    eval_data = {
        "eval_status": "active",
        "dimension_status": f'{{"quality":"{dim_status}"}}',
        "issue_counts": '{"quality":{"total":0,"resolved":0}}',
    }
    monkeypatch.setattr(
        evaluate_context,
        "_load_evaluating_context",
        lambda *_: (
            {"current_state": "Working"},
            tmp_path / "workflow.md",
            eval_data,
            1,
            1,
            "tech",
        ),
    )
    monkeypatch.setattr(session_binding, "_dispatch_dim_allowed", lambda *_: True)
    monkeypatch.setattr(session_binding, "_load_corpus", lambda *_: None)
    monkeypatch.setattr(session_binding, "_canonical_dim", lambda *_: "quality")
    monkeypatch.setattr(
        review_binding,
        "_review_path_from_context",
        lambda *_, **__: review_path,
    )


def _empty_probe_review(path: Path) -> Path:
    path.write_text(
        _render_probe_review(
            dimension_label="Quality",
            dimension_id="quality",
            round_token="round-1",
            active_doc=1,
            evaluate_round=1,
            method_focus="quality",
            handling_policy="class-default",
            findings=[],
        ),
        encoding="utf-8",
    )
    return path


def test_check_dimension_accepts_complete_when_review_exists(
    tmp_path: Path,
    monkeypatch,
):
    review_path = _empty_probe_review(tmp_path / "quality.md")
    _patch_check_dimension_context(
        monkeypatch,
        tmp_path,
        dim_status="complete",
        review_path=review_path,
    )

    result = check_dimension("cycle", tmp_path, dim="quality")

    assert result["ok"] is True
    assert result["outcome"] == "probed"
    assert result["dim_status"] == "complete"
    assert result["issues"] == []


def test_check_dimension_rejects_remediating_when_review_exists(
    tmp_path: Path,
    monkeypatch,
):
    review_path = _empty_probe_review(tmp_path / "quality.md")
    _patch_check_dimension_context(
        monkeypatch,
        tmp_path,
        dim_status="remediating",
        review_path=review_path,
    )

    result = check_dimension("cycle", tmp_path, dim="quality")

    assert result["ok"] is False
    assert "expected 'probed' or 'complete'" in result["reason"]
    assert "did not complete" not in result["reason"]

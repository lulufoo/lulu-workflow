"""Slice 2B tests for the unified apply-remediation transaction."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import eval_control  # noqa: E402
import evaluate_context  # noqa: E402
import probe_control  # noqa: E402
import remediation_control  # noqa: E402
import review_binding  # noqa: E402
import session_binding  # noqa: E402
from remediation_control import (  # noqa: E402
    restore_eval_target,
)
from eval_control import (  # noqa: E402
    apply_remediation,
    begin_dimension_remediation,
    check_dimension_remediation,
    submit_probe_findings,
)
from eval_operation_context import issue_remediation_context  # noqa: E402
from eval_operation_record_schema import (  # noqa: E402
    add_operation_record,
    get_operation_record,
    load_operation_records,
)
from remediation_schema import (  # noqa: E402
    application_submission_digest,
    canonicalize_remediation_application,
    final_digest,
    proposal_digest,
)
from review_io import parse_review_file  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_crash_hook():
    eval_control._CRASH_AFTER_PHASE.set(None)
    yield
    eval_control._CRASH_AFTER_PHASE.set(None)


_DIFF = "--- a/target.md\n+++ b/target.md\n@@ -1 +1 @@\n-old\n+new\n"
_CHANGED_DIFF = "--- a/target.md\n+++ b/target.md\n@@ -1 +1 @@\n-old\n+human-new\n"
_NOOP_DIFF = "--- a/target.md\n+++ b/target.md\n@@ -1 +1 @@\n-old\n+old\n"


def _sha(content: str | bytes) -> str:
    payload = content if isinstance(content, bytes) else content.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _finding(
    issue_id: str,
    *,
    root_cause: str = "WO-ERROR",
    sot_ref: str = "—",
) -> dict[str, str]:
    finding = {
        "id": issue_id,
        "root_cause": root_cause,
        "location": f"target.md:{issue_id}",
        "severity": "medium",
        "evidence": "old",
        "description": f"issue {issue_id}",
    }
    if sot_ref != "—":
        finding["sot_ref"] = sot_ref
    return finding


class _TargetAdapter:
    """Test adapter that implements the Slice 2B EvalTarget protocol."""

    def __init__(self, target_path: Path):
        self.target_path = target_path
        self.commits = 0
        self.restores = 0

    def read_eval_target_digest(self, cycle_id, project_root, *, target_path):
        del cycle_id, project_root
        return _sha(Path(target_path).read_bytes())

    def commit_eval_target(
        self,
        cycle_id,
        project_root,
        *,
        staged_target_path,
        base_digest,
        lease_id,
    ):
        del cycle_id, project_root, lease_id
        live = _sha(self.target_path.read_bytes())
        if live != base_digest:
            return {"ok": False, "error": "stale target"}
        self.target_path.write_bytes(Path(staged_target_path).read_bytes())
        self.commits += 1
        return {"ok": True}

    def restore_eval_target(
        self,
        cycle_id,
        project_root,
        *,
        snapshot_path,
        expected_current_digest,
        lease_id,
    ):
        del cycle_id, project_root, lease_id
        live = _sha(self.target_path.read_bytes())
        if live != expected_current_digest:
            return {
                "ok": False,
                "error": "cas_rejected: live digest is not expected_current",
            }
        self.target_path.write_bytes(Path(snapshot_path).read_bytes())
        self.restores += 1
        return {"ok": True}


def _eval_data() -> dict[str, str]:
    return {
        "eval_capability": "full-remediation",
        "eval_phase": "remediation",
        "eval_status": "active",
        "round_token": "round-1",
        "dimension_status": '{"quality":"remediating"}',
        "issue_counts": '{"quality":{"total":1,"resolved":0}}',
        "total_issues": "1",
        "resolved_issues": "0",
    }


def _install_apply_context(
    monkeypatch,
    tmp_path: Path,
    adapter: _TargetAdapter,
    eval_data: dict[str, str],
    *,
    commit_error: list[str] | None = None,
):
    eval_control._ADAPTER_CTX.set(adapter)
    monkeypatch.setattr(
        remediation_control,
        "_remediation_command_context",
        lambda *_args, **_kwargs: (
            {"current_state": "Working"},
            eval_data,
            1,
            1,
            {
                "evaluate_dir": tmp_path.as_posix(),
                "write_staging_dir": (tmp_path / "staging").as_posix(),
                "evaluate_state": (tmp_path / "evaluate-state.md").as_posix(),
                "lease_id": "lease-1",
                "session_key": "session-1",
            },
        ),
    )
    monkeypatch.setattr(
        review_binding,
        "_review_path_from_context",
        lambda *_args, **_kwargs: tmp_path / "quality.md",
    )
    monkeypatch.setattr(session_binding, "_load_corpus", lambda *_args, **_kwargs: {})

    def _commit(*_args, update=None, patch=None, **_kwargs):
        if commit_error:
            return commit_error.pop(0)
        if update is not None:
            eval_data.update(update(dict(eval_data)))
        elif patch is not None:
            eval_data.update(patch)
        return None

    monkeypatch.setattr(evaluate_context, "_commit_staged_evaluate_state", _commit)


def _install_dimension_context(
    monkeypatch,
    tmp_path: Path,
    adapter: _TargetAdapter,
    eval_data: dict[str, str],
    *,
    commit_error: list[str] | None = None,
):
    _install_apply_context(
        monkeypatch,
        tmp_path,
        adapter,
        eval_data,
        commit_error=commit_error,
    )
    monkeypatch.setattr(
        session_binding,
        "_canonical_dim",
        lambda *_args, **_kwargs: "quality",
    )
    dim_def = {
        "id": "quality",
        "eval_target": {"path": str(tmp_path / "target.md")},
        "method": {"ref": "method", "focus": "quality"},
        "sots": [],
    }
    monkeypatch.setattr(
        session_binding,
        "_expanded_corpus",
        lambda *_args, **_kwargs: {"dimensions": [dim_def]},
    )
    monkeypatch.setattr(
        session_binding,
        "_dimension_def",
        lambda *_args, **_kwargs: dim_def,
    )
    monkeypatch.setattr(
        session_binding,
        "_load_corpus",
        lambda *_args, **_kwargs: {"dimensions": [{"id": "quality"}]},
    )


def _install_committed_probe(monkeypatch, review_path: Path) -> None:
    findings = [
        {
            "id": row["id"],
            "root_cause": row["root_cause"],
            "handling_mode": row["handling_mode"],
        }
        for row in parse_review_file(review_path)
    ]
    real_ops = session_binding._operations_for_round

    def _with_probe(paths, round_token):
        records = list(real_ops(paths, round_token))
        if not any(
            record.get("operation_kind") == "probe"
            and record.get("dimension_id") == "quality"
            for record in records
        ):
            records.append({
                "round_token": round_token,
                "operation_token": "probe-quality",
                "dimension_id": "quality",
                "operation_kind": "probe",
                "phase": "committed",
                "canonical_findings": findings,
            })
        return records

    monkeypatch.setattr(session_binding, "_operations_for_round", _with_probe)


def _write_pending_review(
    tmp_path: Path,
    findings: list[dict[str, str]],
    *,
    handling_modes: dict[str, str],
) -> tuple[Path, Path]:
    target = tmp_path / "target.md"
    target.write_text("old\n", encoding="utf-8")
    review_path = tmp_path / "quality.md"
    content = probe_control._render_probe_review(
        dimension_label="Quality",
        dimension_id="quality",
        round_token="round-1",
        active_doc=1,
        evaluate_round=1,
        method_focus="quality",
        handling_policy="class-default",
        findings=findings,
    )
    for issue_id, mode in handling_modes.items():
        content = content.replace(
            f"| {issue_id} | {next(item['root_cause'] for item in findings if item['id'] == issue_id)} | direct |",
            f"| {issue_id} | {next(item['root_cause'] for item in findings if item['id'] == issue_id)} | {mode} |",
        )
    review_path.write_text(content, encoding="utf-8")
    return target, review_path


def _open_remediation_records(tmp_path: Path) -> list[dict]:
    return [
        record
        for record in load_operation_records(
            tmp_path / "eval-operations.json",
        )["operations"].values()
        if record.get("operation_kind") == "remediation"
        and record.get("phase") == "context-open"
    ]


def _seed_remediation(
    tmp_path: Path,
    findings: list[dict[str, str]],
    *,
    handling_modes: dict[str, str],
    allowed: dict[str, list[str]],
):
    target = tmp_path / "target.md"
    target.write_text("old\n", encoding="utf-8")
    review_path = tmp_path / "quality.md"
    content = probe_control._render_probe_review(
        dimension_label="Quality",
        dimension_id="quality",
        round_token="round-1",
        active_doc=1,
        evaluate_round=1,
        method_focus="quality",
        handling_policy="class-default",
        findings=findings,
    )
    for issue_id, mode in handling_modes.items():
        content = content.replace(
            f"| {issue_id} | {next(item['root_cause'] for item in findings if item['id'] == issue_id)} | direct |",
            f"| {issue_id} | {next(item['root_cause'] for item in findings if item['id'] == issue_id)} | {mode} |",
        )
    review_path.write_text(content, encoding="utf-8")
    context = issue_remediation_context(
        operations_path=tmp_path / "eval-operations.json",
        write_staging_dir=tmp_path / "staging",
        target_path=target,
        review_path=review_path,
        round_token="round-1",
        dimension_id="quality",
        method={"ref": "method", "focus": "quality"},
        sots=[],
        required_issue_ids=[finding["id"] for finding in findings],
        handling_modes_by_issue=handling_modes,
        allowed_decisions_by_issue=allowed,
    )
    return context, target, review_path


def _application_file(tmp_path: Path, application: dict) -> Path:
    path = tmp_path / "application.json"
    path.write_text(json.dumps(application), encoding="utf-8")
    return path


def _direct_application(operation: dict, *, diff: str = _DIFF) -> dict:
    issue_id = operation["required_issue_ids"][0]
    proposal = {
        "round_token": operation["round_token"],
        "operation_token": operation["operation_token"],
        "target_base_digest": operation["target_base_digest"],
        "review_base_digest": operation["review_base_digest"],
        "proposals": [{
            "issue_id": issue_id,
            "proposed_decision": "fix",
            "resolution": "apply the proposed correction",
        }],
        "mutation": {"issue_ids": [issue_id], "unified_diff": diff},
    }
    return {
        "proposal": proposal,
        "human_gate": None,
        "final": {
            "outcome": "apply",
            "resolutions": [{
                "issue_id": issue_id,
                "decision": "fix",
                "resolution": "apply the proposed correction",
            }],
            "mutation": copy.deepcopy(proposal["mutation"]),
        },
    }


def _gated_application(
    operation: dict,
    *,
    decision: str,
    resolution: str,
    mutation: dict | None,
    changed_diff: bool = False,
) -> dict:
    issue_id = operation["required_issue_ids"][0]
    if mutation is None:
        proposal_mutation = None
    else:
        proposal_mutation = copy.deepcopy(mutation)
    proposal = {
        "round_token": operation["round_token"],
        "operation_token": operation["operation_token"],
        "target_base_digest": operation["target_base_digest"],
        "review_base_digest": operation["review_base_digest"],
        "proposals": [{
            "issue_id": issue_id,
            "proposed_decision": decision,
            "resolution": resolution,
        }],
        "mutation": proposal_mutation,
    }
    final_mutation = copy.deepcopy(proposal_mutation)
    if changed_diff and isinstance(final_mutation, dict):
        final_mutation["unified_diff"] = _CHANGED_DIFF
    final = {
        "outcome": "apply",
        "resolutions": [{
            "issue_id": issue_id,
            "decision": decision,
            "resolution": (
                "human confirmed correction" if changed_diff else resolution
            ),
        }],
        "mutation": final_mutation,
    }
    return {
        "proposal": proposal,
        "human_gate": {
            "proposal_digest": proposal_digest(operation, proposal),
            "final_digest": final_digest(operation, final),
            "issue_ids": [issue_id],
            "actor": "human",
            "recorded_at": "2026-08-16T13:00:00+08:00",
            "approves_full_mutation": changed_diff,
        },
        "final": final,
    }


def _mixed_application(
    operation: dict,
    *,
    abandon: bool = False,
    changed_diff: bool = False,
) -> dict:
    proposal = {
        "round_token": operation["round_token"],
        "operation_token": operation["operation_token"],
        "target_base_digest": operation["target_base_digest"],
        "review_base_digest": operation["review_base_digest"],
        "proposals": [
            {
                "issue_id": "q-1",
                "proposed_decision": "fix",
                "resolution": "apply direct correction",
            },
            {
                "issue_id": "q-2",
                "proposed_decision": "fix",
                "resolution": "apply gated correction",
            },
        ],
        "mutation": {"issue_ids": ["q-1", "q-2"], "unified_diff": _DIFF},
    }
    if abandon:
        final = {
            "outcome": "abandon",
            "resolutions": [{
                "issue_id": "q-2",
                "decision": "escalate",
                "resolution": "requires upstream decision",
            }],
            "proposals": [copy.deepcopy(proposal["proposals"][0])],
            "mutation": None,
        }
    else:
        final_mutation = copy.deepcopy(proposal["mutation"])
        if changed_diff:
            final_mutation["unified_diff"] = _CHANGED_DIFF
        final = {
            "outcome": "apply",
            "resolutions": [
                {
                    "issue_id": "q-1",
                    "decision": "fix",
                    "resolution": "apply direct correction",
                },
                {
                    "issue_id": "q-2",
                    "decision": "fix",
                    "resolution": (
                        "human confirmed correction"
                        if changed_diff
                        else "apply gated correction"
                    ),
                },
            ],
            "mutation": final_mutation,
        }
    return {
        "proposal": proposal,
        "human_gate": {
            "proposal_digest": proposal_digest(operation, proposal),
            "final_digest": final_digest(operation, final),
            "issue_ids": ["q-2"],
            "actor": "human",
            "recorded_at": "2026-08-16T13:00:00+08:00",
            "approves_full_mutation": changed_diff,
        },
        "final": final,
    }


def _apply(tmp_path: Path, application: dict) -> dict:
    return apply_remediation(
        "cycle",
        tmp_path,
        application_file=_application_file(tmp_path, application),
    )


def test_direct_wo_apply_resolves_fix_and_mutates_target(tmp_path: Path, monkeypatch):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    eval_data = _eval_data()
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), eval_data)

    result = _apply(tmp_path, _direct_application(operation))

    assert result["ok"] is True, result
    assert result["outcome"] == "apply"
    assert "approved" not in review_path.read_text(encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "new\n"
    row = parse_review_file(review_path)[0]
    assert row["status"] == "resolved"
    assert row["decision"] == "fix"
    assert row["handling_mode"] == "direct"
    assert row["root_cause"] == "WO-ERROR"
    record = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    assert record["phase"] == "committed"
    assert record["target_effect"] == "mutation"
    assert record["submission_digest"] == application_submission_digest(
        operation,
        canonicalize_remediation_application(operation, _direct_application(operation)),
    )
    assert eval_data["dimension_status"] == '{"quality":"complete"}'
    assert json.loads(eval_data["issue_counts"])["quality"]["resolved"] == 1
    assert not (tmp_path / "_human-resolution-txn.json").exists()


def test_human_gated_wo_can_confirm_or_modify_diff(tmp_path: Path, monkeypatch):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "human-gated"},
        allowed={"q-1": ["fix", "accept-divergence", "escalate"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())

    result = _apply(
        tmp_path,
        _gated_application(
            operation,
            decision="fix",
            resolution="apply gated correction",
            mutation={"issue_ids": ["q-1"], "unified_diff": _DIFF},
            changed_diff=True,
        ),
    )

    assert result["ok"] is True, result
    assert target.read_text(encoding="utf-8") == "human-new\n"
    row = parse_review_file(review_path)[0]
    assert row["status"] == "resolved"
    assert row["decision"] == "fix"
    assert row["resolution"] == "human confirmed correction"


def test_human_gated_accept_divergence_does_not_mutate_target(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "human-gated"},
        allowed={"q-1": ["fix", "accept-divergence", "escalate"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    adapter = _TargetAdapter(target)
    _install_apply_context(monkeypatch, tmp_path, adapter, _eval_data())

    result = _apply(
        tmp_path,
        _gated_application(
            operation,
            decision="accept-divergence",
            resolution="intentional difference",
            mutation=None,
        ),
    )

    assert result["ok"] is True, result
    assert target.read_text(encoding="utf-8") == "old\n"
    assert adapter.commits == 0
    record = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    assert record["target_effect"] == "none"
    assert record["target_after_digest"] == record["target_base_digest"]
    row = parse_review_file(review_path)[0]
    assert row["status"] == "resolved"
    assert row["decision"] == "accept-divergence"


@pytest.mark.parametrize("decision", ["select", "allow-multiple"])
def test_decision_required_can_select_or_allow_multiple(
    tmp_path: Path,
    monkeypatch,
    decision: str,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1", root_cause="DECISION-REQUIRED")],
        handling_modes={"q-1": "human-gated"},
        allowed={"q-1": ["select", "allow-multiple", "escalate"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())

    result = _apply(
        tmp_path,
        _gated_application(
            operation,
            decision=decision,
            resolution=f"choose {decision}",
            mutation={"issue_ids": ["q-1"], "unified_diff": _DIFF},
        ),
    )

    assert result["ok"] is True, result
    assert parse_review_file(review_path)[0]["decision"] == decision
    assert target.read_text(encoding="utf-8") == "new\n"


def test_sot_defect_cannot_silently_write_target(tmp_path: Path, monkeypatch):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1", root_cause="SOT-DEFECT", sot_ref="spec.md")],
        handling_modes={"q-1": "human-gated"},
        allowed={"q-1": ["escalate"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    adapter = _TargetAdapter(target)
    eval_data = _eval_data()
    _install_apply_context(monkeypatch, tmp_path, adapter, eval_data)
    application = _gated_application(
        operation,
        decision="escalate",
        resolution="upstream defect",
        mutation=None,
    )
    application["final"] = {
        "outcome": "abandon",
        "resolutions": [{
            "issue_id": "q-1",
            "decision": "escalate",
            "resolution": "upstream defect",
        }],
        "proposals": [],
        "mutation": None,
    }
    application["human_gate"]["final_digest"] = final_digest(
        operation,
        application["final"],
    )

    result = _apply(tmp_path, application)

    assert result["ok"] is True, result
    assert target.read_text(encoding="utf-8") == "old\n"
    assert adapter.commits == 0
    assert parse_review_file(review_path)[0]["decision"] == "escalate"
    assert eval_data["eval_status"] == "abandoned"


def test_mixed_batch_covers_direct_and_human_gated(tmp_path: Path, monkeypatch):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1"), _finding("q-2")],
        handling_modes={"q-1": "direct", "q-2": "human-gated"},
        allowed={
            "q-1": ["fix"],
            "q-2": ["fix", "accept-divergence", "escalate"],
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())

    result = _apply(tmp_path, _mixed_application(operation, changed_diff=True))

    assert result["ok"] is True, result
    assert target.read_text(encoding="utf-8") == "human-new\n"
    rows = parse_review_file(review_path)
    assert [row["status"] for row in rows] == ["resolved", "resolved"]
    assert [row["handling_mode"] for row in rows] == ["direct", "human-gated"]


def test_abandon_resolves_only_escalated_and_abandons_round(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1"), _finding("q-2")],
        handling_modes={"q-1": "direct", "q-2": "human-gated"},
        allowed={
            "q-1": ["fix"],
            "q-2": ["fix", "accept-divergence", "escalate"],
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    adapter = _TargetAdapter(target)
    eval_data = _eval_data()
    _install_apply_context(monkeypatch, tmp_path, adapter, eval_data)

    result = _apply(tmp_path, _mixed_application(operation, abandon=True))

    assert result["ok"] is True, result
    assert result["outcome"] == "abandon"
    assert target.read_text(encoding="utf-8") == "old\n"
    assert adapter.commits == 0
    rows = parse_review_file(review_path)
    assert rows[0]["status"] == "pending"
    assert rows[0]["decision"] == "—"
    assert rows[1]["status"] == "resolved"
    assert rows[1]["decision"] == "escalate"
    assert eval_data["eval_status"] == "abandoned"
    assert eval_data["eval_phase"] == "done"
    record = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    assert record["phase"] == "committed"
    assert record["target_effect"] == "none"


def test_all_direct_final_must_equal_proposal(tmp_path: Path, monkeypatch):
    context, target, _review = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    application = _direct_application(operation)
    application["final"]["resolutions"][0]["resolution"] = "rewritten"

    result = _apply(tmp_path, application)

    assert result["ok"] is False
    assert "all-direct final must equal proposal" in result["reason"]
    assert get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )["phase"] == "context-open"
    assert target.read_text(encoding="utf-8") == "old\n"


def test_human_gated_cannot_rewrite_direct_decision(tmp_path: Path, monkeypatch):
    context, target, _review = _seed_remediation(
        tmp_path,
        [_finding("q-1"), _finding("q-2")],
        handling_modes={"q-1": "direct", "q-2": "human-gated"},
        allowed={
            "q-1": ["fix"],
            "q-2": ["fix", "accept-divergence", "escalate"],
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    application = _mixed_application(operation)
    application["final"]["resolutions"][0]["resolution"] = "changed direct"
    application["human_gate"]["final_digest"] = final_digest(
        operation,
        application["final"],
    )

    result = _apply(tmp_path, application)

    assert result["ok"] is False
    assert "direct issue" in result["reason"]


def test_human_gate_receipt_and_full_mutation_approval_are_required(
    tmp_path: Path,
    monkeypatch,
):
    context, target, _review = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "human-gated"},
        allowed={"q-1": ["fix", "accept-divergence", "escalate"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    application = _gated_application(
        operation,
        decision="fix",
        resolution="apply gated correction",
        mutation={"issue_ids": ["q-1"], "unified_diff": _DIFF},
        changed_diff=True,
    )

    missing = copy.deepcopy(application)
    missing["human_gate"] = None
    assert "human_gate" in _apply(tmp_path, missing)["reason"]

    mismatched = copy.deepcopy(application)
    mismatched["human_gate"]["proposal_digest"] = "0" * 64
    assert "proposal_digest" in _apply(tmp_path, mismatched)["reason"]

    blocked_gate = copy.deepcopy(application)
    blocked_gate["human_gate"]["approves_full_mutation"] = False
    assert "approves_full_mutation" in _apply(tmp_path, blocked_gate)["reason"]


def test_apply_revalidates_embedded_proposal(tmp_path: Path, monkeypatch):
    context, target, _review = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    application = _direct_application(operation)
    application["proposal"]["proposals"][0]["proposed_decision"] = "select"

    result = _apply(tmp_path, application)

    assert result["ok"] is False
    assert "embedded proposal invalid" in result["reason"]


def test_noop_or_empty_diff_is_rejected(tmp_path: Path, monkeypatch):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    before = review_path.read_bytes()

    result = _apply(tmp_path, _direct_application(operation, diff=_NOOP_DIFF))

    assert result["ok"] is False
    assert target.read_text(encoding="utf-8") == "old\n"
    assert review_path.read_bytes() == before
    assert get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )["phase"] == "context-open"


@pytest.mark.parametrize("stale", ["target", "review"])
def test_stale_base_rejects_before_any_publish(tmp_path: Path, monkeypatch, stale: str):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    if stale == "target":
        target.write_text("changed\n", encoding="utf-8")
    else:
        review_path.write_text(
            review_path.read_text(encoding="utf-8") + "\n<!-- stale -->\n",
            encoding="utf-8",
        )
    before_target = target.read_bytes()
    before_review = review_path.read_bytes()

    result = _apply(tmp_path, _direct_application(operation))

    assert result["ok"] is False
    assert "stale" in result["reason"]
    assert target.read_bytes() == before_target
    assert review_path.read_bytes() == before_review
    assert get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )["phase"] == "context-open"


def test_same_payload_replay_is_idempotent(tmp_path: Path, monkeypatch):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    application = _direct_application(operation)

    first = _apply(tmp_path, application)
    target_after = target.read_bytes()
    review_after = review_path.read_bytes()
    second = _apply(tmp_path, application)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["idempotent"] is True
    assert target.read_bytes() == target_after
    assert review_path.read_bytes() == review_after


def test_same_token_different_payload_conflicts(tmp_path: Path, monkeypatch):
    context, target, _review = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    first = _direct_application(operation)
    assert _apply(tmp_path, first)["ok"] is True
    second = _direct_application(operation)
    second["final"]["resolutions"][0]["resolution"] = "different"
    second["proposal"]["proposals"][0]["resolution"] = "different"

    result = _apply(tmp_path, second)

    assert result["ok"] is False
    assert "conflict" in result["reason"]


@pytest.mark.parametrize(
    ("effect", "crash_phase"),
    [
        ("mutation", "prepared"),
        ("mutation", "target-applied"),
        ("mutation", "review-applied"),
        ("none", "prepared"),
        ("none", "target-applied"),
        ("none", "review-applied"),
    ],
)
def test_crash_boundaries_recover_forward(
    tmp_path: Path,
    monkeypatch,
    effect: str,
    crash_phase: str,
):
    gated = effect == "none"
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "human-gated" if gated else "direct"},
        allowed={
            "q-1": (
                ["fix", "accept-divergence", "escalate"] if gated else ["fix"]
            ),
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    adapter = _TargetAdapter(target)
    eval_data = _eval_data()
    _install_apply_context(monkeypatch, tmp_path, adapter, eval_data)
    application = (
        _gated_application(
            operation,
            decision="accept-divergence",
            resolution="intentional difference",
            mutation=None,
        )
        if gated
        else _direct_application(operation)
    )
    eval_control._CRASH_AFTER_PHASE.set(crash_phase)
    with pytest.raises(RuntimeError, match=crash_phase):
        _apply(tmp_path, application)
    record = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    assert record["phase"] == crash_phase
    if effect == "none" or crash_phase == "prepared":
        assert target.read_text(encoding="utf-8") == "old\n"
    else:
        assert target.read_text(encoding="utf-8") == "new\n"
    if crash_phase == "review-applied":
        assert parse_review_file(review_path)[0]["status"] == "resolved"
    else:
        assert parse_review_file(review_path)[0]["status"] == "pending"

    eval_control._CRASH_AFTER_PHASE.set(None)
    recovered = _apply(tmp_path, application)
    assert recovered["ok"] is True, recovered
    record = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    assert record["phase"] == "committed"
    if effect == "none":
        assert target.read_text(encoding="utf-8") == "old\n"
        assert adapter.commits == 0
    else:
        assert target.read_text(encoding="utf-8") == "new\n"
    assert parse_review_file(review_path)[0]["status"] == "resolved"


def test_unknown_digest_during_recovery_is_repair_required(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    application = _direct_application(operation)
    eval_control._CRASH_AFTER_PHASE.set("prepared")
    with pytest.raises(RuntimeError, match="prepared"):
        _apply(tmp_path, application)
    review_path.write_text("unexpected external content\n", encoding="utf-8")
    eval_control._CRASH_AFTER_PHASE.set(None)

    result = _apply(tmp_path, application)

    assert result["ok"] is False
    assert "repair_required" in result["reason"]
    assert target.read_text(encoding="utf-8") == "old\n"


def test_none_effect_stale_target_does_not_publish_disposition(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "human-gated"},
        allowed={"q-1": ["fix", "accept-divergence", "escalate"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), _eval_data())
    target.write_text("stale-live\n", encoding="utf-8")
    before = review_path.read_bytes()

    result = _apply(
        tmp_path,
        _gated_application(
            operation,
            decision="accept-divergence",
            resolution="intentional difference",
            mutation=None,
        ),
    )

    assert result["ok"] is False
    assert "stale" in result["reason"]
    assert review_path.read_bytes() == before
    assert parse_review_file(review_path)[0]["status"] == "pending"


def test_abandon_crash_after_prepared_still_never_mutates(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1"), _finding("q-2")],
        handling_modes={"q-1": "direct", "q-2": "human-gated"},
        allowed={
            "q-1": ["fix"],
            "q-2": ["fix", "accept-divergence", "escalate"],
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    adapter = _TargetAdapter(target)
    eval_data = _eval_data()
    _install_apply_context(monkeypatch, tmp_path, adapter, eval_data)
    application = _mixed_application(operation, abandon=True)
    eval_control._CRASH_AFTER_PHASE.set("prepared")
    with pytest.raises(RuntimeError, match="prepared"):
        _apply(tmp_path, application)
    assert target.read_text(encoding="utf-8") == "old\n"
    eval_control._CRASH_AFTER_PHASE.set(None)

    recovered = _apply(tmp_path, application)

    assert recovered["ok"] is True, recovered
    assert target.read_text(encoding="utf-8") == "old\n"
    assert adapter.commits == 0
    rows = parse_review_file(review_path)
    assert rows[0]["status"] == "pending"
    assert rows[1]["decision"] == "escalate"
    assert eval_data["eval_status"] == "abandoned"


def test_projection_pending_does_not_rollback_and_retries_on_next_entry(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    eval_data = _eval_data()
    _install_apply_context(
        monkeypatch,
        tmp_path,
        _TargetAdapter(target),
        eval_data,
        commit_error=["state rejected"],
    )
    application = _direct_application(operation)

    failed = _apply(tmp_path, application)
    assert failed["ok"] is False
    assert "projection_pending" in failed["reason"]
    record = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    assert record["phase"] == "committed"
    assert target.read_text(encoding="utf-8") == "new\n"
    assert parse_review_file(review_path)[0]["status"] == "resolved"
    assert eval_data["resolved_issues"] == "0"

    retried = _apply(tmp_path, application)
    assert retried["ok"] is True, retried
    assert json.loads(eval_data["issue_counts"])["quality"]["resolved"] == 1
    assert eval_data["dimension_status"] == '{"quality":"complete"}'


def test_restore_is_cas_safe(tmp_path: Path, monkeypatch):
    target = tmp_path / "target.md"
    target.write_text("live-new\n", encoding="utf-8")
    snapshot = tmp_path / "snapshot.md"
    snapshot.write_text("old\n", encoding="utf-8")
    adapter = _TargetAdapter(target)
    eval_control._ADAPTER_CTX.set(adapter)
    monkeypatch.setattr(
        session_binding,
        "_paths_from_handoff",
        lambda: {"lease_id": "lease-1"},
    )

    rejected = restore_eval_target(
        "cycle",
        tmp_path,
        snapshot_path=snapshot,
        expected_current_digest=_sha("old\n"),
        target_path=target,
    )
    assert rejected["ok"] is False
    assert "cas_rejected" in rejected["reason"]
    assert target.read_text(encoding="utf-8") == "live-new\n"

    restored = restore_eval_target(
        "cycle",
        tmp_path,
        snapshot_path=snapshot,
        expected_current_digest=_sha("live-new\n"),
        target_path=target,
    )
    assert restored["ok"] is True
    assert target.read_text(encoding="utf-8") == "old\n"


def _seed_probe(tmp_path: Path) -> dict:
    target = tmp_path / "target.md"
    target.write_text("old\n", encoding="utf-8")
    token = "probe-1"
    snapshot = tmp_path / "staging" / "dimensions" / token / "target.snapshot"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("old\n", encoding="utf-8")
    record = {
        "round_token": "round-1",
        "operation_token": token,
        "dimension_id": "quality",
        "operation_kind": "probe",
        "phase": "context-open",
        "target_base_digest": _sha("old\n"),
        "review_before_exists": False,
        "review_base_digest": None,
        "submission_digest": None,
        "target_effect": None,
        "target_after_digest": None,
        "review_after_digest": None,
        "target_path": target.resolve().as_posix(),
        "snapshot_path": snapshot.as_posix(),
        "resolved_method": {"ref": "method", "focus": "quality"},
        "resolved_sots": [],
        "evidence_snapshots": {},
        "allowed_submission": "finding",
    }
    add_operation_record(tmp_path / "eval-operations.json", record)
    return record


def _install_probe_context(monkeypatch, tmp_path: Path, adapter: _TargetAdapter):
    eval_data = {
        "eval_capability": "full-remediation",
        "eval_phase": "probe",
        "eval_status": "active",
        "round_token": "round-1",
        "dimension_status": '{"quality":"probing"}',
        "handling_policy": '{"quality":"class-default"}',
        "issue_counts": "{}",
    }
    eval_control._ADAPTER_CTX.set(adapter)
    monkeypatch.setattr(
        evaluate_context,
        "_load_evaluating_context",
        lambda *_args, **_kwargs: (
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
        lambda *_args, **_kwargs: {
            "evaluate_dir": tmp_path.as_posix(),
            "write_staging_dir": (tmp_path / "staging").as_posix(),
            "lease_id": "",
            "session_key": "session-1",
        },
    )
    monkeypatch.setattr(
        session_binding,
        "_evaluate_state_path",
        lambda *_args, **_kwargs: tmp_path / "evaluate-state.md",
    )
    monkeypatch.setattr(
        session_binding,
        "_expanded_corpus",
        lambda *_args, **_kwargs: {
            "dimensions": [{
                "id": "quality",
                "label": "Quality",
                "method": {"focus": "quality"},
                "review": {"output_path": "quality.md"},
            }],
        },
    )
    monkeypatch.setattr(
        session_binding,
        "_dimension_def",
        lambda *_args, **_kwargs: {
            "id": "quality",
            "label": "Quality",
            "method": {"focus": "quality"},
            "review": {"output_path": "quality.md"},
        },
    )
    monkeypatch.setattr(session_binding, "_load_corpus", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        evaluate_context,
        "_commit_staged_evaluate_state",
        lambda *_args, **_kwargs: None,
    )
    return eval_data


def _probe_payload(tmp_path: Path) -> Path:
    path = tmp_path / "probe.json"
    path.write_text(
        json.dumps({
            "dimension_token": "probe-1",
            "findings": [_finding("q-1")],
        }),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("crash_phase", ["prepared", "target-applied", "review-applied"])
def test_probe_crash_boundaries_recover_forward(
    tmp_path: Path,
    monkeypatch,
    crash_phase: str,
):
    _seed_probe(tmp_path)
    target = tmp_path / "target.md"
    _install_probe_context(monkeypatch, tmp_path, _TargetAdapter(target))
    payload = _probe_payload(tmp_path)
    eval_control._CRASH_AFTER_PHASE.set(crash_phase)
    with pytest.raises(RuntimeError, match=crash_phase):
        submit_probe_findings("cycle", tmp_path, payload_file=payload)
    record = get_operation_record(tmp_path / "eval-operations.json", "probe-1")
    assert record["phase"] == crash_phase
    assert target.read_text(encoding="utf-8") == "old\n"
    review_path = tmp_path / "quality.md"
    if crash_phase == "review-applied":
        assert review_path.is_file()
    else:
        assert not review_path.exists()

    eval_control._CRASH_AFTER_PHASE.set(None)
    recovered = submit_probe_findings("cycle", tmp_path, payload_file=payload)
    assert recovered["ok"] is True, recovered
    assert get_operation_record(
        tmp_path / "eval-operations.json",
        "probe-1",
    )["phase"] == "committed"
    assert review_path.is_file()
    assert parse_review_file(review_path)[0]["handling_mode"] == "direct"


def test_probe_unknown_review_digest_is_repair_required(tmp_path: Path, monkeypatch):
    record = _seed_probe(tmp_path)
    target = tmp_path / "target.md"
    _install_probe_context(monkeypatch, tmp_path, _TargetAdapter(target))
    payload = _probe_payload(tmp_path)
    eval_control._CRASH_AFTER_PHASE.set("prepared")
    with pytest.raises(RuntimeError, match="prepared"):
        submit_probe_findings("cycle", tmp_path, payload_file=payload)
    review_path = tmp_path / "quality.md"
    review_path.write_text("unknown review bytes\n", encoding="utf-8")
    eval_control._CRASH_AFTER_PHASE.set(None)

    result = submit_probe_findings("cycle", tmp_path, payload_file=payload)

    assert result["ok"] is False
    assert "repair_required" in result["reason"]
    assert get_operation_record(
        tmp_path / "eval-operations.json",
        record["operation_token"],
    )["phase"] == "prepared"


def test_control_uses_new_target_protocol_methods(tmp_path: Path, monkeypatch):
    context, target, _review = _seed_remediation(
        tmp_path,
        [_finding("q-1")],
        handling_modes={"q-1": "direct"},
        allowed={"q-1": ["fix"]},
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    adapter = _TargetAdapter(target)
    _install_apply_context(monkeypatch, tmp_path, adapter, _eval_data())

    result = _apply(tmp_path, _direct_application(operation))

    assert result["ok"] is True, result
    assert adapter.commits == 1


def test_begin_refuses_new_context_after_committed_abandon_even_if_projection_pending(
    tmp_path: Path,
    monkeypatch,
):
    findings = [_finding("q-1"), _finding("q-2")]
    handling = {"q-1": "direct", "q-2": "human-gated"}
    context, target, review_path = _seed_remediation(
        tmp_path,
        findings,
        handling_modes=handling,
        allowed={
            "q-1": ["fix"],
            "q-2": ["fix", "accept-divergence", "escalate"],
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    eval_data = _eval_data()
    _install_dimension_context(
        monkeypatch,
        tmp_path,
        _TargetAdapter(target),
        eval_data,
        commit_error=["state rejected"],
    )
    _install_committed_probe(monkeypatch, review_path)

    failed = _apply(tmp_path, _mixed_application(operation, abandon=True))
    assert failed["ok"] is False
    assert "projection_pending" in failed["reason"]
    assert eval_data["eval_status"] == "active"
    assert eval_data["eval_phase"] == "remediation"
    assert get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )["phase"] == "committed"

    refused = begin_dimension_remediation("cycle", tmp_path, dim="quality")

    assert refused["ok"] is False, refused
    assert "abandoned" in refused["reason"]
    assert eval_data["eval_status"] == "abandoned"
    assert eval_data["eval_phase"] == "done"
    assert _open_remediation_records(tmp_path) == []
    assert parse_review_file(review_path)[0]["status"] == "pending"


def test_abandon_same_payload_replay_is_idempotent_after_projection(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1"), _finding("q-2")],
        handling_modes={"q-1": "direct", "q-2": "human-gated"},
        allowed={
            "q-1": ["fix"],
            "q-2": ["fix", "accept-divergence", "escalate"],
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    eval_data = _eval_data()
    _install_apply_context(monkeypatch, tmp_path, _TargetAdapter(target), eval_data)
    application = _mixed_application(operation, abandon=True)

    first = _apply(tmp_path, application)
    target_after = target.read_bytes()
    review_after = review_path.read_bytes()
    second = _apply(tmp_path, application)

    assert first["ok"] is True, first
    assert first["outcome"] == "abandon"
    assert eval_data["eval_phase"] == "done"
    assert second["ok"] is True, second
    assert second["idempotent"] is True
    assert second["outcome"] == "abandon"
    assert target.read_bytes() == target_after
    assert review_path.read_bytes() == review_after


def test_check_keeps_abandon_leftover_pending_not_repair_required(
    tmp_path: Path,
    monkeypatch,
):
    context, target, review_path = _seed_remediation(
        tmp_path,
        [_finding("q-1"), _finding("q-2")],
        handling_modes={"q-1": "direct", "q-2": "human-gated"},
        allowed={
            "q-1": ["fix"],
            "q-2": ["fix", "accept-divergence", "escalate"],
        },
    )
    operation = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )
    eval_data = _eval_data()
    _install_dimension_context(
        monkeypatch,
        tmp_path,
        _TargetAdapter(target),
        eval_data,
    )
    _install_committed_probe(monkeypatch, review_path)
    assert _apply(tmp_path, _mixed_application(operation, abandon=True))["ok"] is True

    result = check_dimension_remediation("cycle", tmp_path, dim="quality")

    assert result["ok"] is True, result
    assert "repair_required" not in result.get("reason", "")
    assert result["pending_issue_ids"] == ["q-1"]
    assert eval_data["eval_status"] == "abandoned"
    assert eval_data["eval_phase"] == "done"
    assert parse_review_file(review_path)[0]["status"] == "pending"


def test_begin_keeps_context_open_when_remediating_projection_fails(
    tmp_path: Path,
    monkeypatch,
):
    findings = [_finding("q-1")]
    handling = {"q-1": "direct"}
    target, review_path = _write_pending_review(
        tmp_path,
        findings,
        handling_modes=handling,
    )
    eval_data = _eval_data()
    _install_dimension_context(
        monkeypatch,
        tmp_path,
        _TargetAdapter(target),
        eval_data,
        commit_error=["state rejected"],
    )
    _install_committed_probe(monkeypatch, review_path)

    result = begin_dimension_remediation("cycle", tmp_path, dim="quality")

    assert result["ok"] is False, result
    assert "projection_pending" in result["reason"]
    open_ops = _open_remediation_records(tmp_path)
    assert len(open_ops) == 1
    assert open_ops[0]["phase"] == "context-open"
    assert open_ops[0]["required_issue_ids"] == ["q-1"]

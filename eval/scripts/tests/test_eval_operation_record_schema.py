#!/usr/bin/env python3
"""Tests for the operation-record v4 data contract."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_operation_record_schema import (  # noqa: E402
    OPERATION_RECORDS_VERSION,
    add_operation_record,
    advance_operation_record,
    cancel_operation_record,
    create_remediation_operation_record,
    empty_operation_records,
    get_operation_record,
    load_operation_records,
    save_operation_records,
    validate_operation_phase_transition,
    validate_operation_record,
    validate_operation_records,
)

_DIGEST = "a" * 64


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _json_digest(payload) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()


def _remediation_record(*, phase: str = "context-open") -> dict:
    return {
        "round_token": "round-1",
        "operation_token": "operation-1",
        "dimension_id": "synthetic-quality",
        "operation_kind": "remediation",
        "phase": phase,
        "target_base_digest": _DIGEST,
        "review_before_exists": True,
        "review_base_digest": _digest("review before"),
        "required_issue_ids": ["e2-1", "e2-2"],
        "handling_modes_by_issue": {
            "e2-1": "direct",
            "e2-2": "direct",
        },
        "allowed_decisions_by_issue": {
            "e2-1": ["fix"],
            "e2-2": ["fix"],
        },
        "submission_digest": None,
        "target_effect": None,
        "target_after_digest": None,
        "review_after_digest": None,
        "target_lease_key": "/tmp/target.md",
    }


def _create_remediation(path: Path, record: dict | None = None) -> dict:
    captured = copy.deepcopy(record or _remediation_record())
    return create_remediation_operation_record(
        path,
        operation_token=captured["operation_token"],
        round_token=captured["round_token"],
        dimension_id=captured["dimension_id"],
        target_lease_key=captured["target_lease_key"],
        capture_record=lambda: captured,
    )


def _probe_record() -> dict:
    record = {
        **_remediation_record(),
        "operation_token": "probe-1",
        "operation_kind": "probe",
    }
    for field in (
        "required_issue_ids",
        "handling_modes_by_issue",
        "allowed_decisions_by_issue",
        "target_lease_key",
    ):
        del record[field]
    return record


def _prepared_record(*, operation_kind: str = "remediation") -> dict:
    record = _remediation_record(phase="prepared")
    proposal = {
        "round_token": "round-1",
        "operation_token": "operation-1",
        "target_base_digest": _DIGEST,
        "review_base_digest": _digest("review before"),
        "proposals": [
            {
                "issue_id": "e2-1",
                "proposed_decision": "fix",
                "resolution": "fix first",
            },
            {
                "issue_id": "e2-2",
                "proposed_decision": "fix",
                "resolution": "fix second",
            },
        ],
        "mutation": {
            "issue_ids": ["e2-1", "e2-2"],
            "unified_diff": "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n",
        },
    }
    application = {
        "proposal": proposal,
        "human_gate": None,
        "final": {
            "outcome": "apply",
            "resolutions": [
                {"issue_id": "e2-1", "decision": "fix", "resolution": "fix first"},
                {"issue_id": "e2-2", "decision": "fix", "resolution": "fix second"},
            ],
            "mutation": copy.deepcopy(proposal["mutation"]),
        },
    }
    findings = [{"id": "e2-1", "root_cause": "WO-ERROR"}]
    payload = application if operation_kind == "remediation" else findings
    record.update({
        "operation_kind": operation_kind,
        "submission_digest": _json_digest(payload),
        "target_effect": "mutation" if operation_kind == "remediation" else "none",
        "target_staged_path": (
            "/tmp/staged-target.md" if operation_kind == "remediation" else None
        ),
        "target_after_digest": (
            _digest("target after") if operation_kind == "remediation" else _DIGEST
        ),
        "review_before_content": "review before",
        "review_base_digest": _digest("review before"),
        "review_after_content": "review after",
        "review_after_digest": _digest("review after"),
        "canonical_findings": findings if operation_kind == "probe" else None,
        "remediation_application": (
            application
            if operation_kind == "remediation"
            else None
        ),
    })
    if operation_kind == "probe":
        for field in (
            "required_issue_ids",
            "handling_modes_by_issue",
            "allowed_decisions_by_issue",
        ):
            del record[field]
    return record


class TestOperationRecordSchema:
    def test_empty_records_uses_v4(self):
        assert OPERATION_RECORDS_VERSION == "4"
        assert empty_operation_records() == {"version": "4", "operations": {}}

    @pytest.mark.parametrize("operation_kind", ["probe", "remediation"])
    def test_only_unified_operation_kinds_are_valid(self, operation_kind: str):
        record = _remediation_record()
        record["operation_kind"] = operation_kind
        if operation_kind == "probe":
            for field in (
                "required_issue_ids",
                "handling_modes_by_issue",
                "allowed_decisions_by_issue",
            ):
                del record[field]
        assert validate_operation_record(record) == []

    @pytest.mark.parametrize("operation_kind", ["human-resolution", "artifact-remediation"])
    def test_old_operation_kinds_are_rejected(self, operation_kind: str):
        record = _remediation_record()
        record["operation_kind"] = operation_kind
        assert any(
            "invalid operation_kind" in error
            for error in validate_operation_record(record)
        )

    @pytest.mark.parametrize(
        "phase",
        [
            "context-open",
            "prepared",
            "target-applied",
            "review-applied",
            "committed",
            "cancelled",
        ],
    )
    def test_unified_phase_enum(self, phase: str):
        record = (
            _remediation_record(phase=phase)
            if phase in {"context-open", "cancelled"}
            else {**_prepared_record(), "phase": phase}
        )
        assert validate_operation_record(record) == []

    def test_remediation_issue_maps_must_exactly_cover_required_ids(self):
        record = _remediation_record()
        del record["handling_modes_by_issue"]["e2-2"]
        assert any(
            "handling_modes_by_issue keys must match" in error
            for error in validate_operation_record(record)
        )

    def test_remediation_requires_existing_review_with_valid_base_digest(self):
        record = _remediation_record()
        record["review_before_exists"] = False
        record["review_base_digest"] = None
        assert any(
            "remediation operation requires an existing ReviewFile" in error
            for error in validate_operation_record(record)
        )

        record = _remediation_record()
        record["review_base_digest"] = "not-a-digest"
        assert any(
            "review_base_digest" in error
            for error in validate_operation_record(record)
        )

    def test_context_open_cannot_preload_recovery_material(self):
        record = _remediation_record()
        record["review_after_content"] = "premature"
        assert any(
            "review_after_content must be null" in error
            for error in validate_operation_record(record)
        )

    def test_direct_issue_has_only_pre_authorized_fix(self):
        record = _remediation_record()
        record["allowed_decisions_by_issue"]["e2-1"] = ["fix", "accept-divergence"]
        assert any(
            "direct issue" in error for error in validate_operation_record(record)
        )

    @pytest.mark.parametrize(
        ("current", "next_phase", "valid"),
        [
            ("context-open", "prepared", True),
            ("context-open", "cancelled", True),
            ("prepared", "target-applied", True),
            ("target-applied", "review-applied", True),
            ("review-applied", "committed", True),
            ("prepared", "cancelled", False),
            ("review-applied", "target-applied", False),
        ],
    )
    def test_phase_transition_is_strictly_forward(
        self,
        current: str,
        next_phase: str,
        valid: bool,
    ):
        assert (validate_operation_phase_transition(current, next_phase) == []) is valid

    @pytest.mark.parametrize("removed", ["status", "force_human_resolution", "allowed_resolution_kinds"])
    def test_removed_fields_are_rejected(self, removed: str):
        record = _remediation_record()
        record[removed] = "legacy"
        assert f"unsupported field: {removed!r}" in validate_operation_record(record)

    @pytest.mark.parametrize(
        "missing",
        [
            "submission_digest",
            "remediation_application",
            "review_before_exists",
            "review_before_content",
            "review_base_digest",
            "review_after_content",
            "review_after_digest",
            "target_staged_path",
            "target_after_digest",
        ],
    )
    def test_prepared_remediation_requires_complete_recovery_material(
        self,
        missing: str,
    ):
        record = _prepared_record()
        del record[missing]
        assert any(
            missing in error for error in validate_operation_record(record)
        )

    def test_probe_prepared_requires_canonical_findings_not_application(self):
        record = _prepared_record(operation_kind="probe")
        assert validate_operation_record(record) == []
        del record["canonical_findings"]
        assert any(
            "canonical_findings" in error
            for error in validate_operation_record(record)
        )

    def test_prepared_submission_digest_covers_canonical_payload(self):
        record = _prepared_record()
        record["remediation_application"]["final"]["resolutions"][0][
            "resolution"
        ] = "tampered"
        assert any(
            "submission_digest" in error
            for error in validate_operation_record(record)
        )

    @pytest.mark.parametrize(
        ("field", "replacement"),
        [
            ("review_base_digest", "0" * 64),
            ("review_after_digest", "0" * 64),
        ],
    )
    def test_review_exact_content_must_match_digest(
        self,
        field: str,
        replacement: str,
    ):
        record = _prepared_record()
        record[field] = replacement
        assert any(
            "content digest mismatch" in error
            for error in validate_operation_record(record)
        )

    def test_no_target_effect_uses_base_digest_and_no_staged_path(self):
        record = _prepared_record()
        record.update({
            "target_effect": "none",
            "target_staged_path": "/tmp/should-not-exist",
            "target_after_digest": _digest("changed"),
        })
        errors = validate_operation_record(record)
        assert any("target_staged_path must be null" in error for error in errors)
        assert any("target_after_digest must equal target_base_digest" in error for error in errors)


class TestOperationRecordDocument:
    @pytest.mark.parametrize("version", ["2", "3", "5", None])
    def test_old_or_unknown_versions_are_stably_rejected(self, version: str | None):
        data = {"version": version, "operations": {}}
        assert any("incompatible_round" in error for error in validate_operation_records(data))

    def test_old_version_is_rejected_before_operation_fields_are_read(self):
        assert validate_operation_records({
            "version": "3",
            "operations": {"legacy": "legacy-shape"},
        }) == [
            "incompatible_round: operation-record version '3' is not supported "
            "(expected '4')",
        ]

    def test_operation_map_key_matches_operation_token(self):
        record = _remediation_record()
        data = {"version": "4", "operations": {"wrong-token": record}}
        assert any("operation_token must equal map key" in error for error in validate_operation_records(data))

    def test_load_rejects_old_document_without_migration(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        path.write_text(json.dumps({"version": "3", "operations": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="incompatible_round"):
            load_operation_records(path)

    def test_validation_is_pure(self):
        record = _remediation_record()
        before = copy.deepcopy(record)
        validate_operation_record(record)
        assert record == before

    def test_nonterminal_remediation_target_lease_is_unique(self):
        first = _remediation_record()
        second = {
            **_remediation_record(),
            "operation_token": "operation-2",
            "dimension_id": "other-quality",
        }
        errors = validate_operation_records({
            "version": "4",
            "operations": {
                "operation-1": first,
                "operation-2": second,
            },
        })
        assert any("target_lease_key" in error and "operation-1" in error for error in errors)

    def test_terminal_remediation_record_releases_document_lease(self):
        cancelled = {
            **_remediation_record(phase="cancelled"),
            "operation_token": "operation-1",
        }
        current = {
            **_remediation_record(),
            "operation_token": "operation-2",
            "dimension_id": "other-quality",
        }
        assert validate_operation_records({
            "version": "4",
            "operations": {
                "operation-1": cancelled,
                "operation-2": current,
            },
        }) == []


class TestOperationRecordWriters:
    @staticmethod
    def _persist_to_phase(path: Path, phase: str) -> dict:
        _create_remediation(path)
        record = advance_operation_record(path, _prepared_record())
        for next_phase in ("target-applied", "review-applied", "committed"):
            if record["phase"] == phase:
                return record
            record = advance_operation_record(
                path,
                {**record, "phase": next_phase},
            )
        return record

    def test_creation_requires_context_open(self, tmp_path: Path):
        with pytest.raises(ValueError, match="create_remediation_operation_record"):
            add_operation_record(
                tmp_path / "operation-records.json",
                _prepared_record(),
            )

    def test_generic_add_cannot_create_context_open_remediation(self, tmp_path: Path):
        with pytest.raises(ValueError, match="create_remediation_operation_record"):
            add_operation_record(
                tmp_path / "operation-records.json",
                _remediation_record(),
            )

    def test_bulk_writer_cannot_bootstrap_remediation(self, tmp_path: Path):
        with pytest.raises(ValueError, match="create_remediation_operation_record"):
            save_operation_records(
                tmp_path / "operation-records.json",
                {
                    "version": "4",
                    "operations": {"operation-1": _remediation_record()},
                },
            )

    def test_bulk_writer_cannot_append_remediation(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        add_operation_record(path, _probe_record())
        data = load_operation_records(path)
        data["operations"]["operation-1"] = _remediation_record()
        with pytest.raises(ValueError, match="create_remediation_operation_record"):
            save_operation_records(path, data)

    def test_bulk_writer_cannot_create_prepared_history(self, tmp_path: Path):
        with pytest.raises(ValueError, match="create_remediation_operation_record"):
            save_operation_records(
                tmp_path / "operation-records.json",
                {
                    "version": "4",
                    "operations": {"operation-1": _prepared_record()},
                },
            )

    def test_advance_requires_one_legal_step(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        _create_remediation(path)
        skipped = {**_prepared_record(), "phase": "target-applied"}
        with pytest.raises(ValueError, match="phase transition"):
            advance_operation_record(path, skipped)
        assert get_operation_record(path, "operation-1")["phase"] == "context-open"

    def test_advance_preserves_immutable_context(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        _create_remediation(path)
        prepared = _prepared_record()
        prepared["required_issue_ids"] = ["e2-1"]
        prepared["handling_modes_by_issue"] = {"e2-1": "direct"}
        prepared["allowed_decisions_by_issue"] = {"e2-1": ["fix"]}
        with pytest.raises(ValueError, match="immutable context"):
            advance_operation_record(path, prepared)
        assert get_operation_record(path, "operation-1")["required_issue_ids"] == [
            "e2-1",
            "e2-2",
        ]

    def test_advance_persists_prepared_recovery_material(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        _create_remediation(path)
        advanced = advance_operation_record(path, _prepared_record())
        assert advanced["phase"] == "prepared"
        assert advanced["review_after_content"] == "review after"
        assert get_operation_record(path, "operation-1") == advanced

    @pytest.mark.parametrize(
        ("current_phase", "next_phase"),
        [
            ("prepared", "target-applied"),
            ("target-applied", "review-applied"),
            ("review-applied", "committed"),
        ],
    )
    @pytest.mark.parametrize(
        "field",
        [
            "submission_digest",
            "target_effect",
            "target_after_digest",
            "review_after_digest",
            "canonical_findings",
            "remediation_application",
            "review_before_content",
            "review_after_content",
            "target_staged_path",
        ],
    )
    def test_prepared_application_and_recovery_material_is_frozen(
        self,
        tmp_path: Path,
        current_phase: str,
        next_phase: str,
        field: str,
    ):
        path = tmp_path / "operation-records.json"
        current = self._persist_to_phase(path, current_phase)
        replacement = copy.deepcopy(current)
        replacement["phase"] = next_phase
        if field == "remediation_application":
            replacement[field]["final"]["resolutions"][0]["resolution"] = "tampered"
        elif field == "canonical_findings":
            replacement[field] = [{"id": "tampered"}]
        elif field == "target_effect":
            replacement[field] = "none"
        else:
            replacement[field] = f"tampered-{field}"
        with pytest.raises(ValueError, match="prepared material"):
            advance_operation_record(path, replacement)
        assert get_operation_record(path, "operation-1") == current

    def test_bulk_writer_cannot_mutate_prepared_material(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        prepared = self._persist_to_phase(path, "prepared")
        replacement = copy.deepcopy(prepared)
        replacement["phase"] = "target-applied"
        replacement["remediation_application"]["final"]["resolutions"][0][
            "resolution"
        ] = "tampered"
        with pytest.raises(ValueError, match="prepared material"):
            save_operation_records(
                path,
                {
                    "version": "4",
                    "operations": {"operation-1": replacement},
                },
            )
        assert get_operation_record(path, "operation-1") == prepared

    def test_cancel_persists_history_instead_of_deleting(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        _create_remediation(path)
        cancelled = cancel_operation_record(path, "operation-1")
        assert cancelled["phase"] == "cancelled"
        assert get_operation_record(path, "operation-1")["phase"] == "cancelled"
        assert cancel_operation_record(path, "operation-1") == cancelled

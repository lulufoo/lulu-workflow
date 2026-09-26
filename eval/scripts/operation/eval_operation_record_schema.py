#!/usr/bin/env python3
"""Schema and atomic I/O for Eval operation-record v4 documents."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

OPERATION_RECORDS_VERSION = "4"

_OPERATION_KINDS = frozenset({"probe", "remediation"})
_OPERATION_PHASES = frozenset({
    "context-open",
    "prepared",
    "target-applied",
    "review-applied",
    "committed",
    "cancelled",
})
_HANDLING_MODES = frozenset({"direct", "human-gated"})
_DECISIONS = frozenset({
    "fix",
    "accept-divergence",
    "select",
    "allow-multiple",
    "escalate",
})
_TARGET_EFFECTS = frozenset({"none", "mutation"})
_REMOVED_FIELDS = frozenset({
    "status",
    "force_human_resolution",
    "allowed_resolution_kinds",
})
_BASE_REQUIRED_FIELDS = frozenset({
    "round_token",
    "operation_token",
    "dimension_id",
    "operation_kind",
    "phase",
    "target_base_digest",
    "review_before_exists",
    "submission_digest",
    "target_effect",
    "target_after_digest",
    "review_after_digest",
})
_REMEDIATION_REQUIRED_FIELDS = frozenset({
    "review_base_digest",
    "required_issue_ids",
    "handling_modes_by_issue",
    "allowed_decisions_by_issue",
    "target_lease_key",
})
_PREPARED_OR_LATER = frozenset({
    "prepared",
    "target-applied",
    "review-applied",
    "committed",
})
_RECOVERY_FIELDS = frozenset({
    "canonical_findings",
    "remediation_application",
    "review_before_content",
    "review_after_content",
    "target_staged_path",
})
_IMMUTABLE_CONTEXT_FIELDS = frozenset({
    "round_token",
    "operation_token",
    "dimension_id",
    "operation_kind",
    "target_base_digest",
    "target_path",
    "review_before_exists",
    "review_base_digest",
    "required_issue_ids",
    "handling_modes_by_issue",
    "allowed_decisions_by_issue",
    "target_lease_key",
})
_IMMUTABLE_PREPARED_FIELDS = frozenset({
    "submission_digest",
    "target_effect",
    "target_after_digest",
    "review_after_digest",
    *_RECOVERY_FIELDS,
})
_PHASE_TRANSITIONS = {
    "context-open": frozenset({"prepared", "cancelled"}),
    "prepared": frozenset({"target-applied"}),
    "target-applied": frozenset({"review-applied"}),
    "review-applied": frozenset({"committed"}),
    "committed": frozenset(),
    "cancelled": frozenset(),
}


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_unique_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item) for item in value)
        and len(set(value)) == len(value)
    )


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()


def empty_operation_records() -> dict[str, Any]:
    """Return a new empty operation-record document."""
    return {"version": OPERATION_RECORDS_VERSION, "operations": {}}


def validate_operation_phase_transition(current: str, next_phase: str) -> list[str]:
    """Validate one forward phase transition."""
    if current not in _OPERATION_PHASES:
        return [f"invalid current phase: {current!r}"]
    if next_phase not in _PHASE_TRANSITIONS[current]:
        return [f"invalid phase transition: {current!r} -> {next_phase!r}"]
    return []


def validate_operation_record(record: Any) -> list[str]:
    """Return validation errors for one v4 operation record."""
    if not isinstance(record, dict):
        return ["operation record must be an object"]

    errors: list[str] = []
    for field in sorted(_BASE_REQUIRED_FIELDS):
        if field not in record:
            errors.append(f"missing required field: {field!r}")
    for field in sorted(_REMOVED_FIELDS & record.keys()):
        errors.append(f"unsupported field: {field!r}")

    for field in ("round_token", "operation_token", "dimension_id"):
        if field in record and (
            not isinstance(record[field], str) or not record[field]
        ):
            errors.append(f"{field} must be a non-empty string")

    operation_kind = record.get("operation_kind")
    if operation_kind not in _OPERATION_KINDS:
        errors.append(f"invalid operation_kind: {operation_kind!r}")

    phase = record.get("phase")
    if phase not in _OPERATION_PHASES:
        errors.append(f"invalid phase: {phase!r}")

    if not _is_digest(record.get("target_base_digest")):
        errors.append("target_base_digest must be a SHA-256 hex digest")

    review_before_exists = record.get("review_before_exists")
    if not isinstance(review_before_exists, bool):
        errors.append("review_before_exists must be a boolean")
    review_base_digest = record.get("review_base_digest")
    if review_before_exists is True and not _is_digest(review_base_digest):
        errors.append(
            "review_base_digest must be a SHA-256 hex digest when review exists",
        )
    if review_before_exists is False and review_base_digest is not None:
        errors.append("review_base_digest must be null when review does not exist")

    if phase in _PREPARED_OR_LATER:
        for field in sorted(_RECOVERY_FIELDS):
            if field not in record:
                errors.append(f"prepared operation requires {field}")
        for field in ("submission_digest", "target_after_digest", "review_after_digest"):
            if not _is_digest(record.get(field)):
                errors.append(f"{field} must be a SHA-256 hex digest")
        if record.get("target_effect") not in _TARGET_EFFECTS:
            errors.append(f"invalid target_effect: {record.get('target_effect')!r}")

        before_content = record.get("review_before_content")
        if review_before_exists is True:
            if not isinstance(before_content, str):
                errors.append("review_before_content must be exact text when review exists")
            elif _content_digest(before_content) != review_base_digest:
                errors.append("review_before_content digest mismatch")
        elif before_content is not None:
            errors.append("review_before_content must be null when review does not exist")

        after_content = record.get("review_after_content")
        if not isinstance(after_content, str):
            errors.append("review_after_content must be exact text")
        elif _content_digest(after_content) != record.get("review_after_digest"):
            errors.append("review_after_content digest mismatch")

        target_effect = record.get("target_effect")
        staged_path = record.get("target_staged_path")
        if target_effect == "none":
            if staged_path is not None:
                errors.append("target_staged_path must be null for target_effect none")
            if record.get("target_after_digest") != record.get("target_base_digest"):
                errors.append(
                    "target_after_digest must equal target_base_digest "
                    "for target_effect none",
                )
        elif target_effect == "mutation":
            if not isinstance(staged_path, str) or not staged_path:
                errors.append(
                    "target_staged_path must be non-empty for target_effect mutation",
                )
            if record.get("target_after_digest") == record.get("target_base_digest"):
                errors.append(
                    "target_after_digest must differ from target_base_digest "
                    "for target_effect mutation",
                )

        findings = record.get("canonical_findings")
        application = record.get("remediation_application")
        payload: Any = None
        if operation_kind == "probe":
            if (
                not isinstance(findings, list)
                or any(not isinstance(finding, dict) for finding in findings)
            ):
                errors.append("probe prepared operation requires canonical_findings")
            if application is not None:
                errors.append("probe prepared operation forbids remediation_application")
            payload = findings
        elif operation_kind == "remediation":
            if not isinstance(application, dict):
                errors.append(
                    "remediation prepared operation requires remediation_application",
                )
            else:
                from remediation_schema import (
                    application_submission_digest,
                    canonicalize_remediation_application,
                    validate_remediation_application,
                )

                application_errors = validate_remediation_application(
                    record,
                    application,
                )
                errors.extend(
                    f"remediation_application invalid: {error}"
                    for error in application_errors
                )
                if canonicalize_remediation_application(
                    record,
                    application,
                ) != application:
                    errors.append("remediation_application must be canonical")
                if application_submission_digest(
                    record,
                    application,
                ) != record.get("submission_digest"):
                    errors.append(
                        "submission_digest does not match canonical payload",
                    )
            if findings is not None:
                errors.append(
                    "remediation prepared operation forbids canonical_findings",
                )
            payload = application
        if (
            payload is not None
            and operation_kind != "remediation"
            and _canonical_digest(payload) != record.get(
            "submission_digest",
            )
        ):
            errors.append("submission_digest does not match canonical payload")
    elif phase in {"context-open", "cancelled"}:
        for field in (
            "submission_digest",
            "target_effect",
            "target_after_digest",
            "review_after_digest",
            *_RECOVERY_FIELDS,
        ):
            if record.get(field) is not None:
                errors.append(f"{field} must be null while phase is {phase}")

    if operation_kind == "remediation":
        if review_before_exists is not True:
            errors.append(
                "remediation operation requires an existing ReviewFile",
            )
        for field in sorted(_REMEDIATION_REQUIRED_FIELDS):
            if field not in record:
                errors.append(f"remediation operation missing field: {field!r}")
        lease_key = record.get("target_lease_key")
        if not isinstance(lease_key, str) or not lease_key:
            errors.append("target_lease_key must be a non-empty normalized path")

        issue_ids = record.get("required_issue_ids")
        if not _is_unique_string_list(issue_ids):
            errors.append("required_issue_ids must be a non-empty unique string array")
            issue_ids = []
        required = set(issue_ids) if isinstance(issue_ids, list) else set()

        modes = record.get("handling_modes_by_issue")
        if not isinstance(modes, dict) or set(modes) != required:
            errors.append("handling_modes_by_issue keys must match required_issue_ids")
            modes = {}
        elif any(mode not in _HANDLING_MODES for mode in modes.values()):
            errors.append("handling_modes_by_issue contains an invalid mode")

        allowed = record.get("allowed_decisions_by_issue")
        if not isinstance(allowed, dict) or set(allowed) != required:
            errors.append("allowed_decisions_by_issue keys must match required_issue_ids")
            allowed = {}
        else:
            for issue_id, decisions in allowed.items():
                if (
                    not _is_unique_string_list(decisions)
                    or any(decision not in _DECISIONS for decision in decisions)
                ):
                    errors.append(
                        f"allowed_decisions_by_issue[{issue_id!r}] is invalid",
                    )
                if modes.get(issue_id) == "direct" and decisions != ["fix"]:
                    errors.append(
                        f"direct issue {issue_id!r} must allow only pre-authorized fix",
                    )

    return errors


def validate_operation_records(data: Any) -> list[str]:
    """Return validation errors for one operation-record document."""
    if not isinstance(data, dict):
        return ["operation records must be an object"]
    if data.get("version") != OPERATION_RECORDS_VERSION:
        return [
            "incompatible_round: operation-record version "
            f"{data.get('version')!r} is not supported "
            f"(expected {OPERATION_RECORDS_VERSION!r})",
        ]
    errors: list[str] = []
    operations = data.get("operations")
    if not isinstance(operations, dict):
        return [*errors, "operations must be an object"]
    active_lease_owners: dict[str, str] = {}
    for token, record in operations.items():
        if not isinstance(token, str) or not token:
            errors.append("operation token must be a non-empty string")
            continue
        errors.extend(
            f"operations[{token!r}]: {error}"
            for error in validate_operation_record(record)
        )
        if isinstance(record, dict) and record.get("operation_token") != token:
            errors.append(
                f"operations[{token!r}]: operation_token must equal map key",
            )
        if (
            isinstance(record, dict)
            and record.get("operation_kind") == "remediation"
            and record.get("phase") not in {"committed", "cancelled"}
            and isinstance(record.get("target_lease_key"), str)
            and record["target_lease_key"]
        ):
            lease_key = record["target_lease_key"]
            owner = active_lease_owners.get(lease_key)
            if owner is None:
                active_lease_owners[lease_key] = token
            else:
                errors.append(
                    f"operations[{token!r}]: target_lease_key {lease_key!r} "
                    f"is already owned by nonterminal remediation operation "
                    f"{owner!r}",
                )
    return errors


def load_operation_records(path: Path) -> dict[str, Any]:
    """Load v4 records, returning an empty document only when absent."""
    if not path.exists():
        return empty_operation_records()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid operation records JSON: {path}: {exc}") from exc
    errors = validate_operation_records(data)
    if errors:
        raise ValueError(f"operation records invalid ({path}): {'; '.join(errors)}")
    return data


def _write_operation_records(path: Path, data: dict[str, Any]) -> None:
    errors = validate_operation_records(data)
    if errors:
        raise ValueError(f"operation records invalid: {'; '.join(errors)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _validate_context_immutable(
    current: dict[str, Any],
    replacement: dict[str, Any],
) -> None:
    changed = [
        field
        for field in sorted(_IMMUTABLE_CONTEXT_FIELDS)
        if current.get(field) != replacement.get(field)
    ]
    if changed:
        raise ValueError(
            f"immutable context fields changed: {', '.join(changed)}",
        )


def _validate_prepared_material_immutable(
    current: dict[str, Any],
    replacement: dict[str, Any],
) -> None:
    if current.get("phase") not in _PREPARED_OR_LATER:
        return
    changed = [
        field
        for field in sorted(_IMMUTABLE_PREPARED_FIELDS)
        if current.get(field) != replacement.get(field)
    ]
    if changed:
        raise ValueError(
            f"prepared material fields changed: {', '.join(changed)}",
        )


def save_operation_records(path: Path, data: dict[str, Any]) -> None:
    """Persist records without creating advanced phases or rewriting history."""
    if not path.exists():
        errors = validate_operation_records(data)
        if errors:
            raise ValueError(f"operation records invalid: {'; '.join(errors)}")
        if any(
            record.get("operation_kind") == "remediation"
            for record in data["operations"].values()
        ):
            raise ValueError(
                "new remediation operations require "
                "create_remediation_operation_record",
            )
        if any(
            record.get("phase") != "context-open"
            for record in data["operations"].values()
        ):
            raise ValueError("operation creation requires context-open phase")
        _write_operation_records(path, data)
        return

    existing = load_operation_records(path)
    if (
        not isinstance(data, dict)
        or data.get("version") != OPERATION_RECORDS_VERSION
        or not isinstance(data.get("operations"), dict)
    ):
        errors = validate_operation_records(data)
        raise ValueError(f"operation records invalid: {'; '.join(errors)}")
    if not set(existing["operations"]) <= set(data["operations"]):
        raise ValueError("operation history cannot be deleted")
    for token, replacement in data["operations"].items():
        current = existing["operations"].get(token)
        if current is None:
            if replacement.get("operation_kind") == "remediation":
                raise ValueError(
                    "new remediation operations require "
                    "create_remediation_operation_record",
                )
            if replacement.get("phase") != "context-open":
                raise ValueError("operation creation requires context-open phase")
            continue
        if replacement == current:
            continue
        transition_errors = validate_operation_phase_transition(
            str(current.get("phase")),
            str(replacement.get("phase")),
        )
        if transition_errors:
            raise ValueError(transition_errors[0])
        _validate_context_immutable(current, replacement)
        _validate_prepared_material_immutable(current, replacement)
    errors = validate_operation_records(data)
    if errors:
        raise ValueError(f"operation records invalid: {'; '.join(errors)}")
    _write_operation_records(path, data)


def add_operation_record(path: Path, record: dict[str, Any]) -> None:
    """Atomically add one non-remediation context-open operation record."""
    errors = validate_operation_record(record)
    if errors:
        raise ValueError(f"operation record invalid: {'; '.join(errors)}")
    if record.get("operation_kind") == "remediation":
        raise ValueError(
            "new remediation operations require "
            "create_remediation_operation_record",
        )
    if record.get("phase") != "context-open":
        raise ValueError("operation creation requires context-open phase")
    token = str(record["operation_token"])
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            data = load_operation_records(path)
            if token in data["operations"]:
                raise ValueError(f"operation_token already exists: {token}")
            data["operations"][token] = dict(record)
            _write_operation_records(path, data)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def create_remediation_operation_record(
    path: Path,
    *,
    operation_token: str,
    round_token: str,
    dimension_id: str,
    target_lease_key: str,
    capture_record: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Acquire a target lease and capture bases in one records-file lock."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            data = load_operation_records(path)
            for existing in data["operations"].values():
                if (
                    existing.get("operation_kind") == "remediation"
                    and existing.get("round_token") == round_token
                    and existing.get("dimension_id") == dimension_id
                    and existing.get("phase")
                    not in {"committed", "cancelled"}
                ):
                    return dict(existing)
            for existing in data["operations"].values():
                if (
                    existing.get("operation_kind") == "remediation"
                    and existing.get("target_lease_key") == target_lease_key
                    and existing.get("phase")
                    not in {"committed", "cancelled"}
                ):
                    raise ValueError(
                        "target_busy: remediation target is owned by "
                        f"{existing.get('operation_token')}",
                    )
            if operation_token in data["operations"]:
                raise ValueError(
                    f"operation_token already exists: {operation_token}",
                )
            record = capture_record()
            expected = {
                "operation_token": operation_token,
                "round_token": round_token,
                "dimension_id": dimension_id,
                "operation_kind": "remediation",
                "phase": "context-open",
                "target_lease_key": target_lease_key,
            }
            mismatched = [
                field
                for field, value in expected.items()
                if record.get(field) != value
            ]
            if mismatched:
                raise ValueError(
                    "captured remediation context mismatch: "
                    + ", ".join(mismatched),
                )
            errors = validate_operation_record(record)
            if errors:
                raise ValueError(
                    f"operation record invalid: {'; '.join(errors)}",
                )
            data["operations"][operation_token] = dict(record)
            _write_operation_records(path, data)
            return dict(record)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def get_operation_record(path: Path, operation_token: str) -> dict[str, Any]:
    """Return one operation record or raise a stable missing-token error."""
    record = load_operation_records(path)["operations"].get(operation_token)
    if not isinstance(record, dict):
        raise ValueError(f"unknown operation_token: {operation_token}")
    return dict(record)


def advance_operation_record(
    path: Path,
    replacement: dict[str, Any],
) -> dict[str, Any]:
    """Persist one validated, one-step forward operation transition."""
    token = str(replacement.get("operation_token", ""))
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            data = load_operation_records(path)
            current = data["operations"].get(token)
            if not isinstance(current, dict):
                raise ValueError(f"unknown operation_token: {token}")
            transition_errors = validate_operation_phase_transition(
                str(current.get("phase")),
                str(replacement.get("phase")),
            )
            if transition_errors:
                raise ValueError(transition_errors[0])
            _validate_context_immutable(current, replacement)
            _validate_prepared_material_immutable(current, replacement)
            errors = validate_operation_record(replacement)
            if errors:
                raise ValueError(
                    f"operation record invalid: {'; '.join(errors)}",
                )
            advanced = dict(replacement)
            data["operations"][token] = advanced
            _write_operation_records(path, data)
            return advanced
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def cancel_operation_record(path: Path, operation_token: str) -> dict[str, Any]:
    """Persist context-open cancellation without deleting audit history."""
    current = get_operation_record(path, operation_token)
    if current.get("phase") in {"committed", "cancelled"}:
        return current
    cancelled = dict(current)
    cancelled["phase"] = "cancelled"
    return advance_operation_record(path, cancelled)

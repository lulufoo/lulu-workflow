#!/usr/bin/env python3
"""Script-owned schema and I/O for vNext Eval operation records."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any


OPERATION_RECORDS_VERSION = "3"
_OPERATION_KINDS = frozenset({
    "probe",
    "artifact-remediation",
    "human-resolution",
})
_OPERATION_STATUS = frozenset({"open", "closed"})
_SUBMISSION_KINDS = frozenset({"finding", "unified_diff", "resolution"})
_RESOLUTION_KINDS = frozenset({
    "fix",
    "accept-divergence",
    "select",
    "allow-multiple",
    "escalate",
})
_SHA256_HEX = frozenset("0123456789abcdef")
_REQUIRED_RECORD_FIELDS = frozenset(
    {
        "round_token",
        "dimension_token",
        "dimension_id",
        "operation_kind",
        "staging_scope",
        "snapshot_path",
        "target_digest",
        "resolved_method",
        "resolved_sots",
        "evidence_snapshots",
        "allowed_submission",
        "status",
    },
)


def empty_operation_records() -> dict[str, Any]:
    """Return a new, empty operation-record document."""
    return {"version": OPERATION_RECORDS_VERSION, "operations": {}}


def validate_operation_record(record: Any) -> list[str]:
    """Return validation errors for one operation record."""
    if not isinstance(record, dict):
        return ["operation record must be an object"]
    errors: list[str] = []
    for field in sorted(_REQUIRED_RECORD_FIELDS):
        if field not in record:
            errors.append(f"missing required field: {field!r}")
    for field in (
        "round_token",
        "dimension_token",
        "dimension_id",
        "staging_scope",
        "snapshot_path",
        "target_digest",
    ):
        if field in record and (not isinstance(record[field], str) or not record[field]):
            errors.append(f"{field} must be a non-empty string")
    if record.get("operation_kind") not in _OPERATION_KINDS:
        errors.append(f"invalid operation_kind: {record.get('operation_kind')!r}")
    if record.get("operation_kind") in {
        "artifact-remediation",
        "human-resolution",
    }:
        lease_id = record.get("lease_id")
        if not isinstance(lease_id, str) or not lease_id:
            errors.append("remediation operation requires a non-empty lease_id")
    if record.get("operation_kind") == "human-resolution":
        review_digest = record.get("review_base_digest")
        if (
            not isinstance(review_digest, str)
            or len(review_digest) != 64
            or any(character not in _SHA256_HEX for character in review_digest)
        ):
            errors.append("human-resolution requires review_base_digest")
        if not isinstance(record.get("force_human_resolution"), bool):
            errors.append("human-resolution requires boolean force_human_resolution")
        required_ids = record.get("required_issue_ids")
        if (
            not isinstance(required_ids, list)
            or not required_ids
            or any(not isinstance(issue_id, str) or not issue_id for issue_id in required_ids)
            or len(set(required_ids)) != len(required_ids)
        ):
            errors.append("human-resolution requires unique required_issue_ids")
        allowed = record.get("allowed_resolution_kinds")
        if not isinstance(allowed, dict):
            errors.append("human-resolution requires allowed_resolution_kinds")
        elif isinstance(required_ids, list) and set(allowed) != set(required_ids):
            errors.append("allowed_resolution_kinds keys must match required_issue_ids")
        elif any(
            not isinstance(kinds, list)
            or not kinds
            or any(kind not in _RESOLUTION_KINDS for kind in kinds)
            for kinds in allowed.values()
        ):
            errors.append("allowed_resolution_kinds contains invalid values")
    if record.get("allowed_submission") not in _SUBMISSION_KINDS:
        errors.append(
            f"invalid allowed_submission: {record.get('allowed_submission')!r}",
        )
    if record.get("status") not in _OPERATION_STATUS:
        errors.append(f"invalid status: {record.get('status')!r}")
    if not isinstance(record.get("resolved_method"), dict):
        errors.append("resolved_method must be an object")
    if not isinstance(record.get("resolved_sots"), list):
        errors.append("resolved_sots must be an array")
    evidence_snapshots = record.get("evidence_snapshots")
    if not isinstance(evidence_snapshots, dict):
        errors.append("evidence_snapshots must be an object")
    elif evidence_snapshots:
        for evidence_ref, snapshot in evidence_snapshots.items():
            if not isinstance(evidence_ref, str) or not evidence_ref:
                errors.append("evidence snapshot reference must be a non-empty string")
                continue
            if not isinstance(snapshot, dict):
                errors.append(f"evidence_snapshots[{evidence_ref!r}] must be an object")
                continue
            for field in ("path", "digest"):
                value = snapshot.get(field)
                if not isinstance(value, str) or not value:
                    errors.append(
                        f"evidence_snapshots[{evidence_ref!r}].{field} "
                        "must be a non-empty string",
                    )
            digest = snapshot.get("digest")
            if (
                isinstance(digest, str)
                and (
                    len(digest) != 64
                    or any(character not in _SHA256_HEX for character in digest)
                )
            ):
                errors.append(
                    f"evidence_snapshots[{evidence_ref!r}].digest "
                    "must be a SHA-256 hex digest",
                )
    if record.get("status") == "closed":
        for field in ("submission_digest", "review_digest", "review_path"):
            value = record.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"closed operation requires {field}")
        probe_findings = record.get("probe_findings")
        if probe_findings is not None and (
            record.get("operation_kind") != "probe"
            or not isinstance(probe_findings, list)
            or any(not isinstance(finding, dict) for finding in probe_findings)
        ):
            errors.append("probe_findings must be an array of objects on a probe operation")
        resolution_records = record.get("resolution_records")
        if resolution_records is not None and (
            record.get("operation_kind") != "human-resolution"
            or not isinstance(resolution_records, list)
            or any(not isinstance(resolution, dict) for resolution in resolution_records)
        ):
            errors.append(
                "resolution_records must be an array of objects on a closed "
                "human-resolution operation",
            )
        elif isinstance(resolution_records, list):
            for resolution in resolution_records:
                if set(resolution) != {"issue_ids", "resolution_kind", "resolution"}:
                    errors.append("resolution record has invalid fields")
                    continue
                if resolution.get("resolution_kind") not in _RESOLUTION_KINDS:
                    errors.append("resolution record has invalid resolution_kind")
        for field in ("submission_digest", "review_digest"):
            value = record.get(field)
            if (
                isinstance(value, str)
                and (
                    len(value) != 64
                    or any(character not in _SHA256_HEX for character in value)
                )
            ):
                errors.append(f"{field} must be a SHA-256 hex digest")
    return errors


def validate_operation_records(data: Any) -> list[str]:
    """Return validation errors for an operation-record document."""
    if not isinstance(data, dict):
        return ["operation records must be an object"]
    errors: list[str] = []
    if data.get("version") != OPERATION_RECORDS_VERSION:
        errors.append(
            f"invalid version: {data.get('version')!r} "
            f"(expected {OPERATION_RECORDS_VERSION!r})",
        )
    operations = data.get("operations")
    if not isinstance(operations, dict):
        return [*errors, "operations must be an object"]
    for token, record in operations.items():
        if not isinstance(token, str) or not token:
            errors.append("operation token must be a non-empty string")
            continue
        errors.extend(f"operations[{token!r}]: {error}" for error in validate_operation_record(record))
        if isinstance(record, dict) and record.get("dimension_token") != token:
            errors.append(f"operations[{token!r}]: dimension_token must equal map key")
    return errors


def load_operation_records(path: Path) -> dict[str, Any]:
    """Load a validated records document; return an empty one when absent."""
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


def save_operation_records(path: Path, data: dict[str, Any]) -> None:
    """Atomically persist a validated operation-record document."""
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


def add_operation_record(
    path: Path,
    record: dict[str, Any],
) -> None:
    """Persist one previously validated, unique operation record."""
    errors = validate_operation_record(record)
    if errors:
        raise ValueError(f"operation record invalid: {'; '.join(errors)}")
    token = str(record["dimension_token"])
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            data = load_operation_records(path)
            if token in data["operations"]:
                raise ValueError(f"dimension_token already exists: {token}")
            data["operations"][token] = dict(record)
            save_operation_records(path, data)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def remove_operation_record(path: Path, dimension_token: str) -> dict[str, Any]:
    """Remove and return an open operation that failed before dispatch."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            data = load_operation_records(path)
            record = data["operations"].get(dimension_token)
            if not isinstance(record, dict):
                raise ValueError(f"unknown dimension_token: {dimension_token}")
            if record.get("status") != "open":
                raise ValueError(f"dimension_token is not open: {dimension_token}")
            del data["operations"][dimension_token]
            if data["operations"]:
                save_operation_records(path, data)
            else:
                path.unlink(missing_ok=True)
            return dict(record)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def get_operation_record(path: Path, dimension_token: str) -> dict[str, Any]:
    """Return one operation record or raise a stable missing-token error."""
    record = load_operation_records(path)["operations"].get(dimension_token)
    if not isinstance(record, dict):
        raise ValueError(f"unknown dimension_token: {dimension_token}")
    return dict(record)


def close_operation(
    path: Path,
    *,
    dimension_token: str,
    submission_digest: str,
    review_path: Path,
    review_digest: str,
    probe_findings: list[dict[str, Any]] | None = None,
    resolution_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Close one open operation after all of its Eval-owned writes publish."""
    data = load_operation_records(path)
    record = data["operations"].get(dimension_token)
    if not isinstance(record, dict):
        raise ValueError(f"unknown dimension_token: {dimension_token}")
    if record.get("status") != "open":
        raise ValueError(f"dimension_token is not open: {dimension_token}")

    closed = dict(record)
    closed.update({
        "status": "closed",
        "submission_digest": submission_digest,
        "review_path": review_path.resolve().as_posix(),
        "review_digest": review_digest,
    })
    if probe_findings is not None:
        closed["probe_findings"] = probe_findings
    if resolution_records is not None:
        closed["resolution_records"] = resolution_records
    errors = validate_operation_record(closed)
    if errors:
        raise ValueError(f"operation record invalid: {'; '.join(errors)}")
    data["operations"][dimension_token] = closed
    save_operation_records(path, data)
    return dict(closed)


def close_probe_operation(
    path: Path,
    *,
    dimension_token: str,
    submission_digest: str,
    review_path: Path,
    review_digest: str,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Backward-compatible probe-specific name for ``close_operation``."""
    return close_operation(
        path,
        dimension_token=dimension_token,
        submission_digest=submission_digest,
        review_path=review_path,
        review_digest=review_digest,
        probe_findings=findings,
    )

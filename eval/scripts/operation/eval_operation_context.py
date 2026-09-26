#!/usr/bin/env python3
"""Token-scoped Eval operation context and read-only target snapshots."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path
from typing import Any

from eval_operation_record_schema import (
    add_operation_record,
    cancel_operation_record,
    create_remediation_operation_record,
    get_operation_record,
)


def issue_round_token() -> str:
    """Return an opaque token for one vNext Eval round."""
    return uuid.uuid4().hex


def _snapshot_path(write_staging_dir: Path, dimension_token: str) -> tuple[str, Path]:
    staging_scope = f"dimensions/{dimension_token}"
    return staging_scope, write_staging_dir / staging_scope / "target.snapshot"


def _public_sots(sots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Publish SoT identity: `ref` is the SoT link."""
    return [{"ref": str(sot.get("ref", ""))} for sot in sots]


def issue_probe_context(
    *,
    operations_path: Path,
    write_staging_dir: Path,
    target_path: Path,
    round_token: str,
    dimension_id: str,
    method: dict[str, Any],
    sots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Snapshot B and persist an open probe operation before dispatch."""
    target_bytes = target_path.read_bytes()
    target_digest = hashlib.sha256(target_bytes).hexdigest()
    operation_token = uuid.uuid4().hex
    staging_scope, snapshot_path = _snapshot_path(write_staging_dir, operation_token)
    snapshot_path.parent.mkdir(parents=True, exist_ok=False)
    snapshot_path.write_bytes(target_bytes)

    try:
        public_sots = _public_sots(sots)
        record = {
            "round_token": round_token,
            "operation_token": operation_token,
            "dimension_id": dimension_id,
            "operation_kind": "probe",
            "phase": "context-open",
            "staging_scope": staging_scope,
            "snapshot_path": snapshot_path.as_posix(),
            "target_path": target_path.resolve().as_posix(),
            "target_base_digest": target_digest,
            "review_before_exists": False,
            "review_base_digest": None,
            "submission_digest": None,
            "target_effect": None,
            "target_after_digest": None,
            "review_after_digest": None,
            "resolved_method": dict(method),
            "resolved_sots": [dict(sot) for sot in sots],
            "evidence_snapshots": {},
            "allowed_submission": "finding",
        }
        add_operation_record(operations_path, record)
    except Exception:
        shutil.rmtree(snapshot_path.parent, ignore_errors=True)
        raise

    return {
        "round_token": round_token,
        "operation_token": operation_token,
        "dimension_token": operation_token,
        "dimension_id": dimension_id,
        "operation_kind": "probe",
        "target_base_digest": target_digest,
        "target_digest": target_digest,
        "staging_scope": staging_scope,
        "resolved_method": {
            "ref": str(method.get("ref", "")),
            "focus": str(method.get("focus", "")),
        },
        "resolved_sots": public_sots,
        "allowed_submission": "finding",
    }


def issue_remediation_context(
    *,
    operations_path: Path,
    write_staging_dir: Path,
    target_path: Path,
    round_token: str,
    dimension_id: str,
    method: dict[str, Any],
    sots: list[dict[str, Any]],
    review_path: Path,
    required_issue_ids: list[str],
    handling_modes_by_issue: dict[str, str],
    allowed_decisions_by_issue: dict[str, list[str]],
) -> dict[str, Any]:
    """Snapshot B and atomically acquire one normalized target lease."""
    if not review_path.is_file():
        raise ValueError("remediation requires an existing review_path")
    required = list(required_issue_ids)
    modes = dict(handling_modes_by_issue)
    allowed = {
        issue_id: list(decisions)
        for issue_id, decisions in allowed_decisions_by_issue.items()
    }
    if not required or set(modes) != set(required) or set(allowed) != set(required):
        raise ValueError(
            "remediation requires matching required issues, modes, and permissions",
        )
    target_lease_key = target_path.resolve().as_posix()
    operation_token = uuid.uuid4().hex
    staging_scope, snapshot_path = _snapshot_path(write_staging_dir, operation_token)

    def _capture_record() -> dict[str, Any]:
        target_bytes = target_path.read_bytes()
        review_bytes = review_path.read_bytes()
        target_digest = hashlib.sha256(target_bytes).hexdigest()
        review_digest = hashlib.sha256(review_bytes).hexdigest()
        if (
            target_path.read_bytes() != target_bytes
            or review_path.read_bytes() != review_bytes
        ):
            raise ValueError("target or Review base changed during context capture")
        snapshot_path.parent.mkdir(parents=True, exist_ok=False)
        snapshot_path.write_bytes(target_bytes)
        return {
            "round_token": round_token,
            "operation_token": operation_token,
            "dimension_id": dimension_id,
            "operation_kind": "remediation",
            "phase": "context-open",
            "target_base_digest": target_digest,
            "review_before_exists": True,
            "review_base_digest": review_digest,
            "required_issue_ids": required,
            "handling_modes_by_issue": modes,
            "allowed_decisions_by_issue": allowed,
            "submission_digest": None,
            "target_effect": None,
            "target_after_digest": None,
            "review_after_digest": None,
            "target_lease_key": target_lease_key,
            "staging_scope": staging_scope,
            "snapshot_path": snapshot_path.as_posix(),
            "resolved_method": dict(method),
            "resolved_sots": [dict(sot) for sot in sots],
            "evidence_snapshots": {},
            "allowed_submission": "remediation-application",
        }

    try:
        record = create_remediation_operation_record(
            operations_path,
            operation_token=operation_token,
            round_token=round_token,
            dimension_id=dimension_id,
            target_lease_key=target_lease_key,
            capture_record=_capture_record,
        )
    except Exception:
        shutil.rmtree(snapshot_path.parent, ignore_errors=True)
        raise

    return _public_remediation_context(record)


def _public_remediation_context(record: dict[str, Any]) -> dict[str, Any]:
    """Return the runner-safe immutable portion of one remediation record."""
    token = str(record["operation_token"])
    method = dict(record.get("resolved_method", {}))
    return {
        "round_token": record["round_token"],
        "operation_token": token,
        "dimension_token": token,
        "dimension_id": record["dimension_id"],
        "operation_kind": "remediation",
        "target_base_digest": record["target_base_digest"],
        "target_digest": record["target_base_digest"],
        "review_base_digest": record["review_base_digest"],
        "required_issue_ids": list(record["required_issue_ids"]),
        "handling_modes_by_issue": dict(record["handling_modes_by_issue"]),
        "allowed_decisions_by_issue": {
            issue_id: list(decisions)
            for issue_id, decisions in record["allowed_decisions_by_issue"].items()
        },
        "staging_scope": record["staging_scope"],
        "resolved_method": {
            "ref": str(method.get("ref", "")),
            "focus": str(method.get("focus", "")),
        },
        "resolved_sots": _public_sots(list(record.get("resolved_sots", []))),
        "allowed_submission": "remediation-application",
    }


def discard_operation_context(*, operations_path: Path, dimension_token: str) -> None:
    """Discard an unissued token context after its state publication fails."""
    record = cancel_operation_record(operations_path, dimension_token)
    scope_dir = Path(str(record["snapshot_path"])).parent
    shutil.rmtree(scope_dir, ignore_errors=True)
    try:
        scope_dir.parent.rmdir()
    except OSError:
        pass


def read_target_snapshot(
    *,
    operations_path: Path,
    dimension_token: str,
) -> dict[str, str]:
    """Return the complete B snapshot and verified digest for its open token."""
    record = get_operation_record(operations_path, dimension_token)
    if record.get("phase") != "context-open":
        raise ValueError(f"dimension_token is not open: {dimension_token}")
    snapshot_path = Path(str(record["snapshot_path"]))
    if not snapshot_path.is_file():
        raise ValueError(f"target snapshot missing for dimension_token: {dimension_token}")
    content = snapshot_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != record["target_base_digest"]:
        raise ValueError(f"target snapshot digest mismatch for dimension_token: {dimension_token}")
    return {"content": content, "digest": digest}


def read_evidence_snapshot(
    *,
    operations_path: Path,
    dimension_token: str,
    evidence_ref: str,
) -> dict[str, str]:
    """Return a verified dynamic SoT evidence snapshot for its open token."""
    record = get_operation_record(operations_path, dimension_token)
    if record.get("phase") != "context-open":
        raise ValueError(f"dimension_token is not open: {dimension_token}")
    evidence_snapshots = record.get("evidence_snapshots", {})
    snapshot = evidence_snapshots.get(evidence_ref)
    if not isinstance(snapshot, dict):
        raise ValueError(f"unknown evidence_ref for dimension_token: {evidence_ref}")
    snapshot_path = Path(str(snapshot.get("path", "")))
    if not snapshot_path.is_file():
        raise ValueError(
            f"evidence snapshot missing for dimension_token: {dimension_token}",
        )
    content = snapshot_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != snapshot.get("digest"):
        raise ValueError(
            f"evidence snapshot digest mismatch for dimension_token: {dimension_token}",
        )
    return {"content": content, "digest": digest}

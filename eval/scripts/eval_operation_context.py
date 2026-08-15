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
    get_operation_record,
    remove_operation_record,
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
    dimension_token = uuid.uuid4().hex
    staging_scope, snapshot_path = _snapshot_path(write_staging_dir, dimension_token)
    snapshot_path.parent.mkdir(parents=True, exist_ok=False)
    snapshot_path.write_bytes(target_bytes)

    try:
        public_sots = _public_sots(sots)
        record = {
            "round_token": round_token,
            "dimension_token": dimension_token,
            "dimension_id": dimension_id,
            "operation_kind": "probe",
            "staging_scope": staging_scope,
            "snapshot_path": snapshot_path.as_posix(),
            "target_digest": target_digest,
            "resolved_method": dict(method),
            "resolved_sots": [dict(sot) for sot in sots],
            "evidence_snapshots": {},
            "allowed_submission": "finding",
            "status": "open",
        }
        add_operation_record(operations_path, record)
    except Exception:
        shutil.rmtree(snapshot_path.parent, ignore_errors=True)
        raise

    return {
        "round_token": round_token,
        "dimension_token": dimension_token,
        "dimension_id": dimension_id,
        "operation_kind": "probe",
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
    operation_kind: str,
    lease_id: str,
    method: dict[str, Any],
    sots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Snapshot B and persist an open, token-scoped remediation operation."""
    if operation_kind not in {"artifact-remediation", "human-resolution"}:
        raise ValueError(f"invalid remediation operation kind: {operation_kind!r}")
    if not lease_id:
        raise ValueError("remediation lease_id must be a non-empty string")
    allowed_submission = (
        "unified_diff"
        if operation_kind == "artifact-remediation"
        else "resolution"
    )
    target_bytes = target_path.read_bytes()
    target_digest = hashlib.sha256(target_bytes).hexdigest()
    dimension_token = uuid.uuid4().hex
    staging_scope, snapshot_path = _snapshot_path(write_staging_dir, dimension_token)
    snapshot_path.parent.mkdir(parents=True, exist_ok=False)
    snapshot_path.write_bytes(target_bytes)

    try:
        public_sots = _public_sots(sots)
        add_operation_record(
            operations_path,
            {
                "round_token": round_token,
                "dimension_token": dimension_token,
                "dimension_id": dimension_id,
                "operation_kind": operation_kind,
                "lease_id": lease_id,
                "staging_scope": staging_scope,
                "snapshot_path": snapshot_path.as_posix(),
                "target_digest": target_digest,
                "resolved_method": dict(method),
                "resolved_sots": [dict(sot) for sot in sots],
                "evidence_snapshots": {},
                "allowed_submission": allowed_submission,
                "status": "open",
            },
        )
    except Exception:
        shutil.rmtree(snapshot_path.parent, ignore_errors=True)
        raise

    return {
        "round_token": round_token,
        "dimension_token": dimension_token,
        "dimension_id": dimension_id,
        "operation_kind": operation_kind,
        "target_digest": target_digest,
        "staging_scope": staging_scope,
        "resolved_method": {
            "ref": str(method.get("ref", "")),
            "focus": str(method.get("focus", "")),
        },
        "resolved_sots": public_sots,
        "allowed_submission": allowed_submission,
    }


def discard_operation_context(*, operations_path: Path, dimension_token: str) -> None:
    """Discard an unissued token context after its state publication fails."""
    record = remove_operation_record(operations_path, dimension_token)
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
    if record.get("status") != "open":
        raise ValueError(f"dimension_token is not open: {dimension_token}")
    snapshot_path = Path(str(record["snapshot_path"]))
    if not snapshot_path.is_file():
        raise ValueError(f"target snapshot missing for dimension_token: {dimension_token}")
    content = snapshot_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != record["target_digest"]:
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
    if record.get("status") != "open":
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

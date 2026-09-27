#!/usr/bin/env python3
"""Provider-neutral Eval admission journal, staging, and recovery helpers."""

from __future__ import annotations

import json
import os
import shutil
import uuid
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from corpus_snapshot import (
    SNAPSHOT_DIRNAME,
    load_materialized_corpus,
    materialize_corpus_snapshot,
    publish_snapshot_dir,
    snapshot_dir,
)
from evaluate_state_schema import parse_frontmatter_fields

JOURNAL_NAME = "eval-admission.json"
STAGING_DIRNAME = ".eval-admission"
JOURNAL_VERSION = 1
_VALID_STATUS = frozenset({"preparing", "prepared", "transitioned"})


@dataclass(frozen=True)
class EvalAdmissionContext:
    """Provider-neutral admission facts consumed by Eval Control."""

    admission_root: Path
    session_key: str
    provider_state_fingerprint: str
    previous_phase: str
    target_path: Path
    target_digest: str
    candidate_round: int


def fingerprint_parts(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def journal_path(admission_root: Path) -> Path:
    return Path(admission_root) / JOURNAL_NAME


def staging_root(admission_root: Path, token: str) -> Path:
    return Path(admission_root) / STAGING_DIRNAME / token


def staging_snapshot_dir(admission_root: Path, token: str) -> Path:
    return staging_root(admission_root, token) / SNAPSHOT_DIRNAME


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_journal(admission_root: Path) -> dict[str, Any] | None:
    path = journal_path(admission_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("incompatible_round: admission journal is not JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("incompatible_round: admission journal must be an object")
    return payload


def delete_journal(admission_root: Path) -> None:
    path = journal_path(admission_root)
    if path.is_file():
        path.unlink()
    staging = Path(admission_root) / STAGING_DIRNAME
    if staging.is_dir() and not any(staging.iterdir()):
        staging.rmdir()


def reserve_journal(ctx: EvalAdmissionContext, *, token: str | None = None) -> dict[str, Any]:
    """Create-if-absent the session admission journal in preparing state."""
    path = journal_path(ctx.admission_root)
    existing = load_journal(ctx.admission_root)
    if existing is not None:
        if str(existing.get("session_key")) != ctx.session_key:
            raise ValueError("admission journal session_key mismatch")
        return existing
    issued = token or uuid.uuid4().hex
    payload = {
        "version": JOURNAL_VERSION,
        "status": "preparing",
        "token": issued,
        "session_key": ctx.session_key,
        "candidate_round": int(ctx.candidate_round),
        "previous_phase": ctx.previous_phase,
        "provider_state_fingerprint": ctx.provider_state_fingerprint,
        "target_path": Path(ctx.target_path).resolve().as_posix(),
        "target_digest": ctx.target_digest,
        "snapshot_digest": "",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o644)
    try:
        os.write(fd, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return payload


def update_journal(admission_root: Path, updates: dict[str, Any]) -> dict[str, Any]:
    current = load_journal(admission_root)
    if current is None:
        raise ValueError("admission journal missing")
    merged = dict(current)
    merged.update(updates)
    status = str(merged.get("status") or "")
    if status not in _VALID_STATUS:
        raise ValueError(f"invalid admission journal status: {status!r}")
    _atomic_write_json(journal_path(admission_root), merged)
    return merged


def mark_prepared(
    ctx: EvalAdmissionContext,
    *,
    token: str,
    snapshot_digest: str,
    skip_reasons: dict[str, str] | None = None,
) -> dict[str, Any]:
    current = load_journal(ctx.admission_root)
    if current is None or str(current.get("token")) != token:
        raise ValueError("admission token does not own the journal")
    return update_journal(
        ctx.admission_root,
        {
            "status": "prepared",
            "provider_state_fingerprint": ctx.provider_state_fingerprint,
            "target_digest": ctx.target_digest,
            "target_path": Path(ctx.target_path).resolve().as_posix(),
            "snapshot_digest": snapshot_digest,
            "candidate_round": int(ctx.candidate_round),
            "skip_reasons": dict(skip_reasons or {}),
        },
    )


def mark_transitioned(
    admission_root: Path,
    *,
    token: str,
    provider_state_fingerprint: str | None = None,
) -> dict[str, Any]:
    current = load_journal(admission_root)
    if current is None or str(current.get("token")) != token:
        raise ValueError("admission token does not own the journal")
    updates: dict[str, Any] = {"status": "transitioned"}
    if provider_state_fingerprint:
        updates["provider_state_fingerprint"] = provider_state_fingerprint
    return update_journal(admission_root, updates)


def discard_published_snapshot(evaluate_dir: Path) -> None:
    dest = snapshot_dir(evaluate_dir)
    if dest.exists():
        shutil.rmtree(dest)


def discard_staging(admission_root: Path, token: str) -> None:
    root = staging_root(admission_root, token)
    if root.exists():
        shutil.rmtree(root)


def prepare_snapshot(
    ctx: EvalAdmissionContext,
    *,
    token: str,
    corpus: dict[str, Any],
    method_roots: list[Path],
    sot_roots: list[Path],
    method_must_stay_under: Path | None = None,
) -> dict[str, Any]:
    dest = staging_snapshot_dir(ctx.admission_root, token)
    if dest.exists():
        shutil.rmtree(dest)
    return materialize_corpus_snapshot(
        dest,
        corpus,
        method_roots=method_roots,
        sot_roots=sot_roots,
        method_must_stay_under=method_must_stay_under,
    )


def load_prepared_admission_corpus(
    admission_root: Path,
    *,
    token: str,
    evaluate_dir: Path,
    expected_digest: str,
) -> dict[str, Any]:
    """Load the pinned snapshot corpus; never re-resolve a live corpus."""
    digest = str(expected_digest or "").strip()
    if not digest:
        raise ValueError("admission snapshot digest missing")
    published = snapshot_dir(evaluate_dir)
    if published.is_dir():
        return load_materialized_corpus(published, expected_digest=digest)
    staged = staging_snapshot_dir(admission_root, token)
    if staged.is_dir():
        return load_materialized_corpus(staged, expected_digest=digest)
    raise ValueError("incompatible_round: admission snapshot missing for recovery")


_LEASE_RUNTIME_KEYS = frozenset(
    {"active_lease_id", "write_staging_dir", "updated_at"}
)


def stable_runtime_fingerprint(runtime: dict[str, Any]) -> str:
    """Fingerprint provider runtime without lease / clock fields."""
    stable = {
        key: runtime[key]
        for key in sorted(runtime)
        if key not in _LEASE_RUNTIME_KEYS
    }
    return fingerprint_parts(
        json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str)
    )


def record_handoff_lease(
    admission_root: Path,
    *,
    token: str,
    lease_id: str,
) -> dict[str, Any]:
    current = load_journal(admission_root)
    if current is None or str(current.get("token")) != token:
        raise ValueError("admission token does not own the journal")
    return update_journal(admission_root, {"lease_id": str(lease_id)})


def discard_lease_dir(staging_parent: Path, lease_id: str) -> None:
    if not lease_id:
        return
    target = Path(staging_parent) / lease_id
    if target.is_dir():
        shutil.rmtree(target)


def finalize_admission(admission_root: Path, token: str = "") -> None:
    """Delete this attempt's journal and admission staging (§6.4 Finalize)."""
    if token:
        discard_staging(admission_root, token)
    delete_journal(admission_root)


def evaluate_state_round(evaluate_state_path: Path) -> int | None:
    path = Path(evaluate_state_path)
    if not path.is_file():
        return None
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    raw = fields.get("evaluate_round")
    if raw in (None, ""):
        return 1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def this_attempt_is_committed(
    evaluate_state_path: Path,
    *,
    evaluate_round: int,
) -> bool:
    """True when EvalState is this attempt's commit marker (§6.4)."""
    if not evaluate_state_is_commit_marker(evaluate_state_path):
        return False
    state_round = evaluate_state_round(evaluate_state_path)
    if state_round is None:
        return False
    return state_round == int(evaluate_round)


def _reject_admission_drift(
    journal: dict[str, Any],
    ctx: EvalAdmissionContext,
    *,
    focus_phase: str = "",
) -> None:
    status = str(journal.get("status") or "")
    if str(journal.get("session_key")) != ctx.session_key:
        raise ValueError("admission journal session_key mismatch")
    if int(journal.get("candidate_round") or 0) != int(ctx.candidate_round):
        raise ValueError("admission journal candidate_round mismatch")
    fingerprint = str(journal.get("provider_state_fingerprint") or "")
    target = str(journal.get("target_digest") or "")
    fingerprint_drifted = bool(
        fingerprint and fingerprint != ctx.provider_state_fingerprint
    )
    target_drifted = bool(target and target != ctx.target_digest)
    if not fingerprint_drifted and not target_drifted:
        return
    if status == "preparing":
        discard_staging(ctx.admission_root, str(journal["token"]))
        delete_journal(ctx.admission_root)
        raise ValueError("admission provider state drifted during prepare")
    if target_drifted:
        raise ValueError("admission provider or target drifted after prepare")
    # Transition ran; mark_transitioned has not been persisted yet.
    if fingerprint_drifted and focus_phase == "evaluating" and status == "prepared":
        return
    raise ValueError("admission provider or target drifted after prepare")


def publish_prepared_snapshot(
    admission_root: Path,
    *,
    token: str,
    evaluate_dir: Path,
    expected_digest: str,
) -> Path:
    staged = staging_snapshot_dir(admission_root, token)
    if not staged.is_dir():
        raise ValueError("admission snapshot staging missing")
    load_materialized_corpus(staged, expected_digest=expected_digest)
    published = publish_snapshot_dir(staged, evaluate_dir)
    load_materialized_corpus(published, expected_digest=expected_digest)
    return published


def evaluate_state_is_commit_marker(evaluate_state_path: Path) -> bool:
    path = Path(evaluate_state_path)
    if not path.is_file():
        return False
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    return bool(fields.get("corpus_digest") and fields.get("corpus_snapshot_ref"))


def has_probe_operation(operations_path: Path) -> bool:
    path = Path(operations_path)
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        return True
    return any(
        isinstance(record, dict) and record.get("operation_kind") == "probe"
        for record in records
    )


def can_abort_admission(
    *,
    journal: dict[str, Any],
    token: str,
    evaluate_state_path: Path,
    operations_path: Path,
) -> bool:
    if str(journal.get("token")) != token:
        return False
    journal_round = int(journal.get("candidate_round") or 0)
    if journal_round and this_attempt_is_committed(
        evaluate_state_path,
        evaluate_round=journal_round,
    ):
        return False
    ops = Path(operations_path)
    if has_probe_operation(ops):
        return False
    alt_name = (
        "eval-operations.json"
        if ops.name != "eval-operations.json"
        else "operation-records.json"
    )
    if has_probe_operation(ops.with_name(alt_name)):
        return False
    return True


def recover_admission(
    ctx: EvalAdmissionContext,
    *,
    evaluate_state_path: Path,
    evaluate_dir: Path,
    focus_phase: str,
) -> dict[str, Any]:
    """Return the next admission action from journal identity (§6.4)."""
    journal = load_journal(ctx.admission_root)
    if journal is not None:
        journal_round = int(journal.get("candidate_round") or 0)
        if journal_round != int(ctx.candidate_round):
            finalize_admission(ctx.admission_root, str(journal.get("token") or ""))
            journal = None

    published = snapshot_dir(evaluate_dir)
    if this_attempt_is_committed(
        evaluate_state_path,
        evaluate_round=ctx.candidate_round,
    ):
        fields = parse_frontmatter_fields(
            Path(evaluate_state_path).read_text(encoding="utf-8")
        )
        digest = str(fields.get("corpus_digest") or "")
        if not published.is_dir():
            raise ValueError(
                "incompatible_round: EvalState exists but snapshot is missing"
            )
        load_materialized_corpus(published, expected_digest=digest)
        if journal is not None:
            finalize_admission(ctx.admission_root, str(journal.get("token") or ""))
        return {"action": "committed", "journal": None}

    if journal is None:
        if focus_phase == "evaluating" and not evaluate_state_is_commit_marker(
            evaluate_state_path
        ):
            raise ValueError(
                "incompatible_round: evaluating without EvalState or admission journal",
            )
        return {"action": "fresh", "journal": None}

    _reject_admission_drift(journal, ctx, focus_phase=focus_phase)

    status = str(journal.get("status") or "")
    token = str(journal.get("token") or "")
    if status == "preparing":
        discard_staging(ctx.admission_root, token)
        return {"action": "reprepare", "journal": journal}
    if status == "prepared":
        if focus_phase == "evaluating":
            return {"action": "publish", "journal": journal}
        return {"action": "transition", "journal": journal}
    if status == "transitioned":
        staged = staging_snapshot_dir(ctx.admission_root, token)
        digest = str(journal.get("snapshot_digest") or "")
        if published.is_dir() and digest:
            load_materialized_corpus(published, expected_digest=digest)
            return {"action": "commit-state", "journal": journal}
        if staged.is_dir() and digest:
            return {"action": "publish", "journal": journal}
        raise ValueError(
            "incompatible_round: transitioned admission has no valid snapshot"
        )
    raise ValueError(f"incompatible_round: unknown admission status {status!r}")


def context_as_dict(ctx: EvalAdmissionContext) -> dict[str, Any]:
    payload = asdict(ctx)
    payload["admission_root"] = ctx.admission_root.as_posix()
    payload["target_path"] = Path(ctx.target_path).as_posix()
    return payload

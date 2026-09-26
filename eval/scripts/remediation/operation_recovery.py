"""Forward a prepared Eval operation to committed, or fail closed."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import eval_control as ec
from eval_operation_record_schema import advance_operation_record
from review_io import split_table_row


def validate_live_target_digest(target_path: Path, expected_digest: str) -> None:
    """Reject publication when the live target changed since context capture."""
    actual = hashlib.sha256(target_path.read_bytes()).hexdigest()
    if actual != expected_digest:
        raise ValueError(
            "stale target: live digest does not match operation target_base_digest",
        )


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _target_path_from_record(record: dict[str, Any]) -> Path:
    raw = record.get("target_path") or record.get("target_lease_key")
    if not isinstance(raw, str) or not raw:
        raise ValueError("operation record missing target path")
    return Path(raw)


def _live_target_digest(
    cycle_id: str,
    project_root: Path,
    target_path: Path,
) -> str:
    adapter = ec._adapter()
    reader = getattr(adapter, "read_eval_target_digest", None)
    if callable(reader):
        return str(reader(cycle_id, project_root, target_path=target_path))
    return hashlib.sha256(target_path.read_bytes()).hexdigest()


def _review_live_state(review_path: Path, record: dict[str, Any]) -> str:
    if not review_path.is_file():
        return "before" if record.get("review_before_exists") is not True else "unknown"
    digest = _content_digest(review_path.read_text(encoding="utf-8"))
    if record.get("review_before_exists") is True and digest == record.get(
        "review_base_digest",
    ):
        return "before"
    if digest == record.get("review_after_digest"):
        return "after"
    return "unknown"


def _target_live_state(live_digest: str, record: dict[str, Any]) -> str:
    if record.get("target_effect") == "none":
        return "base" if live_digest == record.get("target_base_digest") else "other"
    if live_digest == record.get("target_base_digest"):
        return "before"
    if live_digest == record.get("target_after_digest"):
        return "after"
    return "unknown"


def _render_review_after(
    before_content: str,
    updates: dict[str, tuple[str, str, str]],
) -> str:
    rendered: list[str] = []
    header_seen = False
    for line in before_content.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            rendered.append(line)
            continue
        cells = split_table_row(stripped)
        if not header_seen:
            header_seen = True
            rendered.append(line)
            continue
        issue_id = cells[0] if cells else ""
        if issue_id in updates and len(cells) >= 11:
            status, decision, resolution = updates[issue_id]
            cells[8] = status
            cells[9] = decision
            cells[10] = resolution
            rendered.append("| " + " | ".join(cells) + " |\n")
        else:
            rendered.append(line)
    return "".join(rendered)


def _publish_review_after(review_path: Path, content: str) -> None:
    ec._atomic_write_review(review_path, content)


def _commit_eval_target(
    cycle_id: str,
    project_root: Path,
    record: dict[str, Any],
    paths: dict[str, str],
) -> None:
    staged = record.get("target_staged_path")
    if not isinstance(staged, str) or not staged:
        raise ValueError("prepared mutation is missing target_staged_path")
    result = ec._adapter().commit_eval_target(
        cycle_id,
        project_root,
        staged_target_path=Path(staged),
        base_digest=str(record["target_base_digest"]),
        lease_id=str(paths.get("lease_id", "")),
    )
    if not result.get("ok"):
        raise ValueError(str(result.get("error") or "commit_eval_target failed"))


def _advance_phase(
    operations_path: Path,
    record: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    advanced = advance_operation_record(operations_path, {**record, "phase": phase})
    ec._crash_after(phase)
    return advanced


def _forward_recover_to_committed(
    cycle_id: str,
    project_root: Path,
    *,
    command: str,
    operations_path: Path,
    record: dict[str, Any],
    paths: dict[str, str],
    review_path: Path,
    evaluate_round: int,
) -> dict[str, Any]:
    """Advance a prepared-or-later operation to committed, or fail closed."""
    review_file = Path(record["review_path"]) if record.get("review_path") else review_path
    target_path = _target_path_from_record(record)
    try:
        live_target = _live_target_digest(cycle_id, project_root, target_path)
    except (OSError, ValueError) as exc:
        return ec._failure(command, f"repair_required: {exc}")
    review_state = _review_live_state(review_file, record)
    target_state = _target_live_state(live_target, record)
    if review_state == "unknown":
        return ec._failure(command, "repair_required: live Review digest is unknown")
    if record.get("target_effect") == "none":
        if target_state != "base":
            return ec._failure(
                command,
                "repair_required: live target is not the verified base digest",
            )
    else:
        if target_state == "unknown":
            return ec._failure(command, "repair_required: live target digest is unknown")
        if target_state == "before" and review_state == "after":
            return ec._failure(
                command,
                "repair_required: target before and Review after",
            )

    try:
        if record.get("phase") == "prepared":
            if record.get("target_effect") == "mutation" and target_state == "before":
                _commit_eval_target(cycle_id, project_root, record, paths)
                target_state = "after"
            record = _advance_phase(operations_path, record, "target-applied")
        if record.get("phase") == "target-applied":
            if review_state == "before":
                if record.get("operation_kind") == "probe":
                    import probe_control
                    publish_error = probe_control._publish_probe_review(
                        cycle_id,
                        project_root,
                        paths=paths,
                        evaluate_round=evaluate_round,
                        formal_review_path=review_file,
                        content=str(record["review_after_content"]),
                    )
                    if publish_error is not None:
                        return ec._failure(command, publish_error)
                else:
                    _publish_review_after(
                        review_file,
                        str(record["review_after_content"]),
                    )
                review_state = "after"
            elif review_state != "after":
                return ec._failure(
                    command,
                    "repair_required: live Review digest is unknown",
                )
            record = _advance_phase(operations_path, record, "review-applied")
        if record.get("phase") == "review-applied":
            record = advance_operation_record(
                operations_path,
                {**record, "phase": "committed"},
            )
    except ValueError as exc:
        reason = str(exc)
        if reason.startswith("repair_required"):
            return ec._failure(command, reason)
        return ec._failure(command, reason)
    return {"ok": True, "record": record}

"""Schema and durable I/O for per-slice fact-production permits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from compose_state_lock import canonical_digest, durable_write_json

PERMIT_STORE_BASENAME = "_fact-production-permits.json"
PERMIT_LOCK_BASENAME = "_fact-production-permits.lock"
PERMIT_STORE_VERSION = 1
PERMIT_STATES = frozenset(
    {"proposed", "acknowledged", "consuming", "consumed", "revoked", "repair_required"}
)


def permit_store_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / PERMIT_STORE_BASENAME


def permit_lock_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / PERMIT_LOCK_BASENAME


def empty_permit_store() -> dict[str, Any]:
    return {
        "version": PERMIT_STORE_VERSION,
        "kind": "fact-production-permits",
        "permits": [],
    }


def validate_permit_store(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["permit store root must be an object"]
    if value.get("version") != PERMIT_STORE_VERSION:
        return [f"permit store version must be {PERMIT_STORE_VERSION}"]
    if value.get("kind") != "fact-production-permits":
        return ["permit store kind must be 'fact-production-permits'"]
    permits = value.get("permits")
    if not isinstance(permits, list):
        return ["permit store permits must be an array"]

    errors: list[str] = []
    seen: set[str] = set()
    for index, permit in enumerate(permits):
        prefix = f"permits[{index}]"
        if not isinstance(permit, dict):
            errors.append(f"{prefix} must be an object")
            continue
        permit_id = permit.get("id")
        if not isinstance(permit_id, str) or not permit_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif permit_id in seen:
            errors.append(f"{prefix}.id duplicate: {permit_id!r}")
        else:
            seen.add(permit_id)
        if permit.get("state") not in PERMIT_STATES:
            errors.append(f"{prefix}.state invalid: {permit.get('state')!r}")
        for field in ("kind", "slice_key", "digest", "payload", "precondition", "snapshot"):
            if field not in permit:
                errors.append(f"{prefix}: missing {field!r}")
    return errors


def load_permit_store(slice_dir: Path) -> dict[str, Any]:
    path = permit_store_path(slice_dir)
    if not path.is_file():
        return empty_permit_store()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid permit store JSON: {exc}") from exc
    errors = validate_permit_store(value)
    if errors:
        raise ValueError("; ".join(errors))
    return value


def save_permit_store(slice_dir: Path, value: dict[str, Any]) -> None:
    errors = validate_permit_store(value)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(permit_store_path(slice_dir), value)


def digest_payload(payload: dict[str, Any]) -> str:
    """Permit v1 canonical payload digest."""
    return canonical_digest(payload)

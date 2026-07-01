#!/usr/bin/env python3
"""Schema and I/O for exposed-points.json (EP ledger).

Each EP represents a candidate design gap discovered during Gate 3.
EPs are appended incrementally as they are registered; status is
updated in-place as they are resolved or deferred.

Required fields per EP:
  id          - EP-NNN (unique, monotone)
  section     - section key (must equal active_section at registration)
  block       - To-Be architecture block it hangs under
  method      - method ID from inductive-scan-criteria, or "human_inlet"
  kw          - KW criterion this EP leaves false
  type        - broken_invariant | undecided | undefined_contract
  description - design gap description
  code_refs   - list of "file::symbol (line)" strings
  confidence  - direct | inferred
  blocking    - bool
  source      - ai_scan | human_inlet
  status      - open | resolved | deferred

Optional fields:
  resolution  - decision text (required when status=resolved)

MUST NOT include a 'tier' field.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EP_STATUSES = frozenset({"open", "resolved", "deferred"})
EP_TYPES = frozenset({"broken_invariant", "undecided", "undefined_contract"})
EP_SOURCES = frozenset({"ai_scan", "human_inlet"})
EP_CONFIDENCES = frozenset({"direct", "inferred"})

_REQUIRED_FIELDS = (
    "id",
    "section",
    "block",
    "method",
    "kw",
    "type",
    "description",
    "code_refs",
    "confidence",
    "blocking",
    "source",
    "status",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_ep(ep: dict[str, Any]) -> list[str]:
    """Return validation error strings for a single EP (empty = valid)."""
    errors: list[str] = []

    if "tier" in ep:
        errors.append(f"EP {ep.get('id')!r}: 'tier' field is forbidden")

    for field in _REQUIRED_FIELDS:
        if field not in ep:
            errors.append(f"EP {ep.get('id')!r}: missing required field {field!r}")

    ep_id = str(ep.get("id", ""))
    if not ep_id.startswith("EP-"):
        errors.append(f"EP id must start with 'EP-', got {ep_id!r}")

    status = str(ep.get("status", "")).lower()
    if status not in EP_STATUSES:
        errors.append(f"EP {ep_id!r}: invalid status {status!r}")

    ep_type = str(ep.get("type", "")).lower()
    if ep_type not in EP_TYPES:
        errors.append(f"EP {ep_id!r}: invalid type {ep_type!r}")

    source = str(ep.get("source", "")).lower()
    if source not in EP_SOURCES:
        errors.append(f"EP {ep_id!r}: invalid source {source!r}")

    confidence = str(ep.get("confidence", "")).lower()
    if confidence not in EP_CONFIDENCES:
        errors.append(f"EP {ep_id!r}: invalid confidence {confidence!r}")

    if not isinstance(ep.get("code_refs"), list):
        errors.append(f"EP {ep_id!r}: code_refs must be a list")

    blocking = ep.get("blocking")
    if not isinstance(blocking, bool):
        errors.append(f"EP {ep_id!r}: blocking must be a bool")

    if status == "resolved" and not ep.get("resolution"):
        errors.append(f"EP {ep_id!r}: resolution is required when status=resolved")

    return errors


def normalize_ep(ep: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized EP dict with canonical field order."""
    return {
        "id": str(ep.get("id", "")),
        "section": str(ep.get("section", "")),
        "block": str(ep.get("block", "")),
        "method": str(ep.get("method", "")),
        "kw": str(ep.get("kw", "")),
        "type": str(ep.get("type", "")),
        "description": str(ep.get("description", "")),
        "code_refs": list(ep.get("code_refs") or []),
        "confidence": str(ep.get("confidence", "")),
        "blocking": bool(ep.get("blocking", False)),
        "source": str(ep.get("source", "")),
        "status": str(ep.get("status", "open")),
        "resolution": ep.get("resolution"),
        "registered_at": ep.get("registered_at") or _now_iso(),
        "updated_at": ep.get("updated_at") or _now_iso(),
    }


def init_ledger() -> dict[str, Any]:
    """Return an empty EP ledger."""
    return {
        "version": "1",
        "eps": [],
        "updated_at": _now_iso(),
    }


def validate_ledger(data: dict[str, Any]) -> list[str]:
    """Return validation error strings for the full ledger."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    eps = data.get("eps")
    if not isinstance(eps, list):
        errors.append("eps must be a list")
        return errors

    seen_ids: set[str] = set()
    for ep in eps:
        if not isinstance(ep, dict):
            errors.append("each ep must be an object")
            continue
        ep_id = str(ep.get("id", ""))
        if ep_id in seen_ids:
            errors.append(f"duplicate EP id: {ep_id!r}")
        seen_ids.add(ep_id)
        errors.extend(validate_ep(ep))

    return errors


def load_ledger(path: Path) -> dict[str, Any]:
    """Load and validate EP ledger from disk. Returns empty ledger if missing."""
    if not path.exists():
        return init_ledger()
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_ledger(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def save_ledger(path: Path, data: dict[str, Any]) -> None:
    """Validate and write EP ledger to disk."""
    errors = validate_ledger(data)
    if errors:
        raise ValueError("; ".join(errors))
    data["updated_at"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def next_ep_id(ledger: dict[str, Any]) -> str:
    """Return the next EP-NNN id based on current ledger contents."""
    eps = ledger.get("eps") or []
    n = len(eps) + 1
    return f"EP-{n:03d}"


def append_ep(ledger: dict[str, Any], ep: dict[str, Any]) -> dict[str, Any]:
    """Validate and append a new EP to the ledger. Returns updated ledger."""
    ep_normalized = normalize_ep(ep)
    errors = validate_ep(ep_normalized)
    if errors:
        raise ValueError("; ".join(errors))
    updated = dict(ledger)
    updated["eps"] = list(ledger.get("eps") or []) + [ep_normalized]
    return updated


def update_ep_status(
    ledger: dict[str, Any],
    ep_id: str,
    *,
    status: str,
    resolution: str | None = None,
) -> dict[str, Any]:
    """Update an existing EP's status and optional resolution."""
    if status not in EP_STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    if status == "resolved" and not resolution:
        raise ValueError("resolution is required when status=resolved")

    updated_eps: list[dict[str, Any]] = []
    found = False
    for ep in ledger.get("eps") or []:
        if ep["id"] == ep_id:
            ep = dict(ep)
            ep["status"] = status
            if resolution is not None:
                ep["resolution"] = resolution
            ep["updated_at"] = _now_iso()
            found = True
        updated_eps.append(ep)

    if not found:
        raise ValueError(f"EP not found: {ep_id!r}")

    updated = dict(ledger)
    updated["eps"] = updated_eps
    return updated


def blocking_open_eps(
    ledger: dict[str, Any], *, section: str | None = None
) -> list[dict[str, Any]]:
    """Return EPs that are blocking=True and status=open.

    If section is given, filter to that section only.
    """
    result: list[dict[str, Any]] = []
    for ep in ledger.get("eps") or []:
        if ep.get("blocking") and str(ep.get("status", "")).lower() == "open":
            if section is None or ep.get("section") == section:
                result.append(ep)
    return result


def eps_for_section(
    ledger: dict[str, Any], section: str
) -> list[dict[str, Any]]:
    """Return all EPs belonging to a section."""
    return [ep for ep in (ledger.get("eps") or []) if ep.get("section") == section]

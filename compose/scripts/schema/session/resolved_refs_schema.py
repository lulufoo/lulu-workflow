#!/usr/bin/env python3
"""Per-revision frozen upstream baseline (①) and resolved ref handoff (②).

At stage start, ``start.py`` writes two per-revision artifacts into the
revision dir (sibling of ``workflow-state.md``):

    ① delivered-refs.json  — verbatim frozen copy of the cycle-level
       delivered-refs.json. The cycle file is shared and *mutable* (every
       upstream delivery upserts it), so a frozen copy is the only stable
       baseline. Audit / traceability only; compose consumers do NOT read it.

    ② resolved-refs.json   — the three provenance refs (scope / intent
       baseline / norm constraint), plus optional ``facts_ref``, that the
       stage resolver settles ONCE at start.
       For decision-holder stages, ``scope_ref.path`` is decision-fact.json
       (required; no prose fallback). Plan←design may still be design-doc.
       This is the ONLY artifact compose consumers read; they never re-derive
       from the mutable cycle file or from workflow-state.

workflow-state.md carries pure session-control state and no longer stores
``delivered_refs``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delivered_refs_schema import DeliveredRef, ref_from_file_entry

FROZEN_DELIVERED_FILE = "delivered-refs.json"
RESOLVED_REFS_FILE = "resolved-refs.json"
_VERSION = "1"


def frozen_delivered_path(revision_dir: Path) -> Path:
    return revision_dir / FROZEN_DELIVERED_FILE


def resolved_refs_path(revision_dir: Path) -> Path:
    return revision_dir / RESOLVED_REFS_FILE


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def freeze_delivered_copy(revision_dir: Path, cycle_data: dict[str, Any]) -> Path:
    """Write ① — verbatim frozen copy of the cycle delivered-refs.json."""
    path = frozen_delivered_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cycle_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _ref_to_dict(ref: DeliveredRef | None) -> dict[str, str] | None:
    return ref.to_dict() if ref is not None else None


def write_resolved_refs(
    revision_dir: Path,
    *,
    cycle_id: str,
    stage: str,
    run_mode: str,
    scope_ref: DeliveredRef | None,
    intent_baseline_refs: list[DeliveredRef],
    norm_constraint_refs: list[DeliveredRef],
    facts_ref: DeliveredRef | None = None,
) -> Path:
    """Write ② — provenance refs plus optional facts_ref."""
    payload = {
        "version": _VERSION,
        "cycle_id": cycle_id,
        "stage": stage,
        "run_mode": run_mode,
        "scope_ref": _ref_to_dict(scope_ref),
        "intent_baseline_refs": [r.to_dict() for r in intent_baseline_refs],
        "norm_constraint_refs": [r.to_dict() for r in norm_constraint_refs],
        "facts_ref": _ref_to_dict(facts_ref),
        "frozen_at": _now_iso(),
    }
    path = resolved_refs_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _ref_from_dict(item: Any) -> DeliveredRef | None:
    if not isinstance(item, dict):
        return None
    dtype = str(item.get("type", "")).strip()
    path = str(item.get("path", "")).strip()
    if not dtype or not path:
        return None
    facts_path = str(item.get("facts_path", "")).strip()
    decision_fact_path = str(item.get("decision_fact_path", "")).strip()
    return DeliveredRef(
        type=dtype,
        path=path,
        facts_path=facts_path,
        decision_fact_path=decision_fact_path,
    )


def _refs_from_list(items: Any) -> list[DeliveredRef]:
    if not isinstance(items, list):
        return []
    out: list[DeliveredRef] = []
    for item in items:
        ref = _ref_from_dict(item)
        if ref is not None:
            out.append(ref)
    return out


def load_resolved_refs(revision_dir: Path) -> dict[str, Any]:
    """Read ② resolved-refs.json; raise if missing or malformed."""
    path = resolved_refs_path(revision_dir)
    if not path.is_file():
        raise FileNotFoundError(f"resolved-refs.json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid resolved-refs.json (not object): {path}")
    return data


def has_resolved_refs(revision_dir: Path) -> bool:
    return resolved_refs_path(revision_dir).is_file()


def resolved_scope_ref(revision_dir: Path) -> DeliveredRef | None:
    return _ref_from_dict(load_resolved_refs(revision_dir).get("scope_ref"))


def resolved_facts_ref(revision_dir: Path) -> DeliveredRef | None:
    return _ref_from_dict(load_resolved_refs(revision_dir).get("facts_ref"))


def is_decision_fact_file(path: Path | str) -> bool:
    """True when path is a readable decision-fact.json (unit scope SSOT)."""
    p = Path(path)
    if not p.is_file():
        return False
    if p.name == "decision-fact.json":
        return True
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("gates"), dict)


def scope_decision_fact_path(revision_dir: Path) -> str | None:
    """Absolute decision-fact path when ``scope_ref`` is the unit SSOT; else None."""
    ref = resolved_scope_ref(revision_dir)
    if ref is None:
        return None
    raw = str(ref.path).strip()
    if not raw or not is_decision_fact_file(raw):
        return None
    return str(Path(raw).resolve())


def resolved_intent_baseline_refs(revision_dir: Path) -> list[DeliveredRef]:
    return _refs_from_list(load_resolved_refs(revision_dir).get("intent_baseline_refs"))


def resolved_norm_constraint_refs(revision_dir: Path) -> list[DeliveredRef]:
    return _refs_from_list(load_resolved_refs(revision_dir).get("norm_constraint_refs"))


def frozen_delivered_path_by_type(revision_dir: Path, delivered_type: str) -> str:
    """Return the ① frozen path for ``delivered_type`` (empty string if absent)."""
    for ref in frozen_delivered_refs(revision_dir):
        if ref.type == delivered_type:
            return ref.path
    return ""


def frozen_delivered_refs(revision_dir: Path) -> list[DeliveredRef]:
    """Return ① frozen upstream stage entries (doc path + optional facts_path)."""
    path = frozen_delivered_path(revision_dir)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return []
    out: list[DeliveredRef] = []
    for dtype in entries:
        key = str(dtype)
        if key.endswith("-facts"):
            continue
        ref = ref_from_file_entry(key, data)
        if ref is not None:
            out.append(ref)
    return out

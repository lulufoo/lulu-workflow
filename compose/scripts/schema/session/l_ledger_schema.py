#!/usr/bin/env python3
"""Schema and I/O for revision ``l-ledger.json``.

On-disk shape (exact keys only — no legacy fields)::

    {
      "version": 1,
      "order": ["L1", "L2"],
      "focus": "L1",
      "by_id": {
        "L1": {"state": "Pending", "frozen": false}
      }
    }

Design rationale:
docs/domain/archive/compose/archive-33.0/compose-outer-shell-management-subdesign.md
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2]
_SECTION = _SCRIPTS / "section"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from compose_state_lock import canonical_digest, durable_write_json

L_LEDGER_FILENAME = "l-ledger.json"
LEDGER_VERSION = 1
STATES = frozenset(
    {
        "Pending",
        "FactIntake",
        "Inductive",
        "Deductive",
        "Writing",
        "FreeEdit",
        "Evaluating",
        "Completed",
    }
)
_ON_DISK_KEYS = frozenset({"version", "order", "focus", "by_id"})
_CELL_KEYS = frozenset({"state", "frozen"})
_L_ID = re.compile(r"^L([1-9][0-9]*)$")
_IN_PROGRESS = frozenset(
    {
        "FactIntake",
        "Inductive",
        "Deductive",
        "Writing",
        "FreeEdit",
        "Evaluating",
    }
)


def l_ledger_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / L_LEDGER_FILENAME


def active_slice_dir(revision_dir: Path) -> Path:
    """Return ``revision/Lx`` for the current ledger focus."""
    rev = Path(revision_dir).resolve()
    ledger = load_l_ledger(rev)
    return (rev / str(ledger["focus"])).resolve()


def working_slice_dir(path: Path) -> Path:
    """Revision root → focus Lx; already-a-slice path is unchanged."""
    root = Path(path).resolve()
    if l_ledger_path(root).is_file():
        return active_slice_dir(root)
    return root


def empty_cell(*, state: str = "Pending", frozen: bool = False) -> dict[str, Any]:
    return {"state": state, "frozen": frozen}


def build_ledger(order: list[str]) -> dict[str, Any]:
    """Start-time ledger: focus L1, every cell Pending and unfrozen."""
    if not order:
        raise ValueError("order must be non-empty")
    payload = {
        "version": LEDGER_VERSION,
        "order": list(order),
        "focus": order[0],
        "by_id": {nid: empty_cell() for nid in order},
    }
    errors = validate_l_ledger(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def ledger_fingerprint(ledger: dict[str, Any]) -> str:
    return canonical_digest(_canonical_payload(ledger))


def focus_state(ledger: dict[str, Any]) -> str:
    return str(ledger["by_id"][str(ledger["focus"])]["state"])


def eval_session_phase(revision_dir: Path) -> str:
    """Eval-facing lowercase phase: ``evaluating`` or ``pending``."""
    try:
        ledger = load_l_ledger(revision_dir)
        if focus_state(ledger) == "Evaluating":
            return "evaluating"
    except (OSError, ValueError, FileNotFoundError, KeyError):
        return "pending"
    return "pending"


def focus_index(ledger: dict[str, Any]) -> int:
    return list(ledger["order"]).index(str(ledger["focus"]))


def frozen_indices(ledger: dict[str, Any]) -> list[int]:
    order = list(ledger["order"])
    by_id = ledger["by_id"]
    return [i for i, nid in enumerate(order) if bool(by_id[nid]["frozen"])]


def reached_frontier(ledger: dict[str, Any]) -> int:
    """Index r = max({focus} ∪ frozen indices). Not persisted."""
    f = focus_index(ledger)
    frozen = frozen_indices(ledger)
    if not frozen:
        return f
    return max([f, *frozen])


def all_completed_unfrozen(ledger: dict[str, Any]) -> bool:
    by_id = ledger["by_id"]
    return all(
        cell["state"] == "Completed" and cell["frozen"] is False
        for cell in by_id.values()
    )


def validate_l_ledger(ledger: Any) -> list[str]:
    if not isinstance(ledger, dict):
        return ["ledger must be an object"]
    errors: list[str] = []
    extra = sorted(set(ledger) - _ON_DISK_KEYS)
    if extra:
        errors.append(f"unknown ledger keys: {', '.join(extra)}")
    missing = sorted(_ON_DISK_KEYS - set(ledger))
    if missing:
        errors.append(f"missing ledger keys: {', '.join(missing)}")
        return errors

    if ledger.get("version") != LEDGER_VERSION:
        errors.append(f"version must be {LEDGER_VERSION}")

    order = ledger.get("order")
    if not isinstance(order, list) or not order:
        errors.append("order must be a non-empty array")
        return errors
    if any(not isinstance(item, str) for item in order):
        errors.append("order items must be strings")
        return errors
    if len(order) != len(set(order)):
        errors.append("order must not contain duplicates")
    expected = [f"L{i}" for i in range(1, len(order) + 1)]
    if order != expected:
        errors.append(f"order must be consecutive L1…Ln, got {order!r}")

    by_id = ledger.get("by_id")
    if not isinstance(by_id, dict):
        errors.append("by_id must be an object")
        return errors
    if set(by_id) != set(order):
        errors.append("by_id keys must equal order")

    focus = ledger.get("focus")
    if not isinstance(focus, str) or focus not in order:
        errors.append("focus must belong to order")

    for nid in order:
        cell = by_id.get(nid)
        where = f"by_id[{nid}]"
        if not isinstance(cell, dict):
            errors.append(f"{where} must be an object")
            continue
        extra_cell = sorted(set(cell) - _CELL_KEYS)
        if extra_cell:
            errors.append(f"{where} unknown keys: {', '.join(extra_cell)}")
        missing_cell = sorted(_CELL_KEYS - set(cell))
        if missing_cell:
            errors.append(f"{where} missing keys: {', '.join(missing_cell)}")
            continue
        if cell.get("state") not in STATES:
            errors.append(f"{where}.state must be one of {sorted(STATES)}")
        if not isinstance(cell.get("frozen"), bool):
            errors.append(f"{where}.frozen must be a boolean")

    if errors:
        return errors
    errors.extend(_global_shape_errors(ledger))
    return errors


def _global_shape_errors(ledger: dict[str, Any]) -> list[str]:
    order = list(ledger["order"])
    by_id = ledger["by_id"]
    focus = str(ledger["focus"])
    f = order.index(focus)
    frozen = [i for i, nid in enumerate(order) if by_id[nid]["frozen"] is True]
    r = f if not frozen else max([f, *frozen])
    errors: list[str] = []

    if by_id[focus]["frozen"] is True:
        errors.append("focus must not be frozen")

    for i, nid in enumerate(order):
        cell = by_id[nid]
        if i < f:
            if cell["state"] != "Completed" or cell["frozen"] is True:
                errors.append(
                    f"{nid}: prefix of focus must be Completed and unfrozen"
                )
        elif i == f:
            if cell["frozen"] is True:
                errors.append(f"{nid}: focus must be unfrozen")
        elif i > r:
            if cell["state"] != "Pending" or cell["frozen"] is True:
                errors.append(
                    f"{nid}: after reached frontier must be Pending and unfrozen"
                )

    if frozen:
        expected = list(range(f + 1, r + 1))
        if frozen != expected:
            errors.append(
                "frozen cells must be the contiguous interval after focus "
                f"(expected {expected}, got {frozen})"
            )
    return errors


def _canonical_payload(ledger: dict[str, Any]) -> dict[str, Any]:
    order = list(ledger["order"])
    by_id = ledger["by_id"]
    return {
        "version": int(ledger["version"]),
        "order": order,
        "focus": str(ledger["focus"]),
        "by_id": {
            nid: {
                "state": by_id[nid]["state"],
                "frozen": bool(by_id[nid]["frozen"]),
            }
            for nid in order
        },
    }


def save_l_ledger(revision_dir: Path, ledger: dict[str, Any]) -> Path:
    errors = validate_l_ledger(ledger)
    if errors:
        raise ValueError("; ".join(errors))
    path = l_ledger_path(revision_dir)
    durable_write_json(path, _canonical_payload(ledger))
    return path


def load_l_ledger(revision_dir: Path) -> dict[str, Any]:
    path = l_ledger_path(revision_dir)
    if not path.is_file():
        raise FileNotFoundError(f"missing l-ledger: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_l_ledger(data)
    if errors:
        raise ValueError("; ".join(errors))
    return _canonical_payload(data)


def in_progress_states() -> frozenset[str]:
    return _IN_PROGRESS

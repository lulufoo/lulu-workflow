#!/usr/bin/env python3
"""Schema and I/O for approach ``node-binding.json`` (archive-1.1 bind/reopen)."""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path
from typing import Any

_DECISION_SCRIPTS = Path(__file__).resolve().parents[3] / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from dec_io import atomic_write_text  # noqa: E402

BINDING_FILENAME = "node-binding.json"
BINDING_VERSION = "1"
BINDING_STATES = frozenset(
    {"preparing", "decision_bound", "bound", "reopen_pending", "failed"}
)
OPERATIONS = frozenset({"enter", "reopen"})
PERMIT_STATES = frozenset({"none", "issued", "consumed"})


def node_binding_path(approach_root: Path) -> Path:
    return Path(approach_root).resolve() / BINDING_FILENAME


def new_binding_id() -> str:
    return f"bind-{secrets.token_hex(8)}"


def build_node_binding(
    *,
    binding_id: str,
    state: str,
    previous: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    context_snapshot: dict[str, str] | None = None,
    frozen_nodes: list[str] | None = None,
    operation: str = "enter",
    permit_path: str | None = None,
    permit_state: str = "none",
    version: str = BINDING_VERSION,
) -> dict[str, Any]:
    prev = previous or {"focus": None, "active_session": None}
    tgt = target or {"node_id": "", "session_dir": ""}
    snap = context_snapshot or {"path": "", "sha256": ""}
    return {
        "version": str(version),
        "binding_id": str(binding_id).strip(),
        "state": str(state).strip(),
        "previous": {
            "focus": None if prev.get("focus") is None else str(prev.get("focus")),
            "active_session": (
                None
                if prev.get("active_session") is None
                else str(prev.get("active_session"))
            ),
        },
        "target": {
            "node_id": str(tgt.get("node_id", "")).strip(),
            "session_dir": str(tgt.get("session_dir", "")).strip(),
        },
        "context_snapshot": {
            "path": str(snap.get("path", "")).strip(),
            "sha256": str(snap.get("sha256", "")).strip(),
        },
        "frozen_nodes": [str(n).strip() for n in (frozen_nodes or [])],
        "operation": str(operation).strip(),
        "permit_path": None if permit_path is None else str(permit_path).strip(),
        "permit_state": str(permit_state).strip(),
    }


def validate_node_binding(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("node-binding must be a JSON object")
    version = str(data.get("version", "")).strip()
    if version != BINDING_VERSION:
        raise ValueError(f"node-binding version must be {BINDING_VERSION!r}, got {version!r}")
    binding_id = str(data.get("binding_id", "")).strip()
    if not binding_id:
        raise ValueError("binding_id is required")
    state = str(data.get("state", "")).strip()
    if state not in BINDING_STATES:
        raise ValueError(
            f"state must be one of {sorted(BINDING_STATES)}, got {state!r}"
        )
    operation = str(data.get("operation", "")).strip()
    if operation not in OPERATIONS:
        raise ValueError(
            f"operation must be one of {sorted(OPERATIONS)}, got {operation!r}"
        )
    permit_state = str(data.get("permit_state", "none")).strip() or "none"
    if permit_state not in PERMIT_STATES:
        raise ValueError(
            f"permit_state must be one of {sorted(PERMIT_STATES)}, got {permit_state!r}"
        )
    previous = data.get("previous")
    if not isinstance(previous, dict):
        raise ValueError("previous must be an object")
    target = data.get("target")
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    node_id = str(target.get("node_id", "")).strip()
    session_dir = str(target.get("session_dir", "")).strip()
    if not node_id or not session_dir:
        raise ValueError("target.node_id and target.session_dir are required")
    snap = data.get("context_snapshot")
    if not isinstance(snap, dict):
        raise ValueError("context_snapshot must be an object")
    frozen = data.get("frozen_nodes")
    if frozen is None:
        frozen_nodes: list[str] = []
    elif isinstance(frozen, list):
        frozen_nodes = [str(n).strip() for n in frozen]
    else:
        raise ValueError("frozen_nodes must be a list")
    permit_raw = data.get("permit_path")
    permit_path = None if permit_raw is None else str(permit_raw).strip() or None
    return build_node_binding(
        binding_id=binding_id,
        state=state,
        previous=previous,
        target={"node_id": node_id, "session_dir": session_dir},
        context_snapshot={
            "path": str(snap.get("path", "")).strip(),
            "sha256": str(snap.get("sha256", "")).strip(),
        },
        frozen_nodes=frozen_nodes,
        operation=operation,
        permit_path=permit_path,
        permit_state=permit_state,
        version=version,
    )


def save_node_binding(approach_root: Path, data: dict[str, Any]) -> Path:
    payload = validate_node_binding(data)
    path = node_binding_path(approach_root)
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    return path


def load_node_binding(approach_root: Path) -> dict[str, Any]:
    path = node_binding_path(approach_root)
    if not path.is_file():
        raise FileNotFoundError(f"node-binding not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("node-binding must be a JSON object")
    return validate_node_binding(raw)


def try_load_node_binding(approach_root: Path) -> dict[str, Any] | None:
    path = node_binding_path(approach_root)
    if not path.is_file():
        return None
    return load_node_binding(approach_root)

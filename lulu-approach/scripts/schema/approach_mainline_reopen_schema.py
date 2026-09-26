#!/usr/bin/env python3
"""Schema and atomic I/O for approach Main/Split reopen transactions."""

from __future__ import annotations

import json
import re
import secrets
import sys
from pathlib import Path
from typing import Any

_DECISION_SCRIPTS = Path(__file__).resolve().parents[3] / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from dec_io import atomic_write_text  # noqa: E402

MAINLINE_REOPEN_FILENAME = "mainline-reopen.json"
MAINLINE_REOPEN_VERSION = "1"
MAINLINE_STATES = frozenset(
    {
        "preparing",
        "downstream_frozen",
        "main_reopen_pending",
        "main_repaired",
        "split_pending",
        "split_review",
        "archive_required",
        "working_retained",
        "working_rebuilt",
        "failed",
    }
)
TERMINAL_STATES = frozenset({"working_retained", "working_rebuilt", "failed"})
_TARGET_KINDS = frozenset({"main", "split"})
_DX_ID_RE = re.compile(r"^D\d+$")
_ON_DISK_KEYS = frozenset(
    {
        "version",
        "transaction_id",
        "target",
        "state",
        "previous",
        "frozen",
        "old_graph_snapshot",
        "candidate_graph_snapshot",
        "candidate_id_mapping",
        "structure_signature",
    }
)


def mainline_reopen_path(approach_root: Path) -> Path:
    """Return the single active Main/Split reopen transaction path."""
    return Path(approach_root).resolve() / MAINLINE_REOPEN_FILENAME


def new_transaction_id() -> str:
    """Return an opaque transaction identifier."""
    return f"mlr-{secrets.token_hex(8)}"


def _snapshot(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def build_mainline_reopen(
    *,
    transaction_id: str,
    target: dict[str, Any],
    state: str,
    previous: dict[str, Any],
    frozen: dict[str, Any],
    old_graph_snapshot: str | None = None,
    candidate_graph_snapshot: str | None = None,
    candidate_id_mapping: dict[str, Any] | None = None,
    structure_signature: dict[str, str | None] | None = None,
    version: str = MAINLINE_REOPEN_VERSION,
) -> dict[str, Any]:
    """Build an unvalidated persisted transaction payload."""
    return {
        "version": str(version).strip(),
        "transaction_id": str(transaction_id).strip(),
        "target": {
            "kind": str(target.get("kind", "")).strip(),
            "node_id": str(target.get("node_id", "")).strip(),
        },
        "state": str(state).strip(),
        "previous": {
            "macro_state": str(previous.get("macro_state", "")).strip(),
            "focus": (
                None
                if previous.get("focus") is None
                else str(previous.get("focus")).strip()
            ),
            "active_session": (
                None
                if previous.get("active_session") is None
                else str(previous.get("active_session")).strip()
            ),
        },
        "frozen": {
            "split": bool(frozen.get("split", False)),
            "nodes": [str(node_id).strip() for node_id in frozen.get("nodes", [])],
        },
        "old_graph_snapshot": _snapshot(old_graph_snapshot),
        "candidate_graph_snapshot": _snapshot(candidate_graph_snapshot),
        "candidate_id_mapping": dict(candidate_id_mapping or {}),
        "structure_signature": {
            "old": _snapshot((structure_signature or {}).get("old")),
            "candidate": _snapshot((structure_signature or {}).get("candidate")),
        },
    }


def validate_mainline_reopen(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a Main/Split transaction."""
    if not isinstance(data, dict):
        raise ValueError("mainline-reopen must be a JSON object")
    extra = set(data) - _ON_DISK_KEYS
    if extra:
        raise ValueError(f"mainline-reopen unexpected keys: {sorted(extra)}")
    version = str(data.get("version", "")).strip()
    if version != MAINLINE_REOPEN_VERSION:
        raise ValueError(
            f"mainline-reopen version must be {MAINLINE_REOPEN_VERSION!r}, got {version!r}"
        )
    transaction_id = str(data.get("transaction_id", "")).strip()
    if not transaction_id:
        raise ValueError("mainline-reopen transaction_id is required")
    target = data.get("target")
    if not isinstance(target, dict):
        raise ValueError("mainline-reopen target must be an object")
    target_kind = str(target.get("kind", "")).strip()
    target_node_id = str(target.get("node_id", "")).strip()
    if target_kind not in _TARGET_KINDS:
        raise ValueError("mainline-reopen target.kind must be main|split")
    if target_node_id != target_kind:
        raise ValueError("mainline-reopen target.node_id must equal target.kind")
    state = str(data.get("state", "")).strip()
    if state not in MAINLINE_STATES:
        raise ValueError(
            f"mainline-reopen state must be one of {sorted(MAINLINE_STATES)}, got {state!r}"
        )
    previous = data.get("previous")
    if not isinstance(previous, dict):
        raise ValueError("mainline-reopen previous must be an object")
    frozen = data.get("frozen")
    if not isinstance(frozen, dict):
        raise ValueError("mainline-reopen frozen must be an object")
    nodes = frozen.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("mainline-reopen frozen.nodes must be a list")
    normalized_nodes = [str(node_id).strip() for node_id in nodes]
    if any(not _DX_ID_RE.match(node_id) for node_id in normalized_nodes):
        raise ValueError("mainline-reopen frozen.nodes must contain only D<number>")
    if len(set(normalized_nodes)) != len(normalized_nodes):
        raise ValueError("mainline-reopen frozen.nodes must be unique")
    mapping = data.get("candidate_id_mapping", {})
    if not isinstance(mapping, dict):
        raise ValueError("mainline-reopen candidate_id_mapping must be an object")
    signature = data.get("structure_signature", {})
    if not isinstance(signature, dict) or set(signature) - {"old", "candidate"}:
        raise ValueError("mainline-reopen structure_signature must contain old|candidate")
    return build_mainline_reopen(
        transaction_id=transaction_id,
        target={"kind": target_kind, "node_id": target_node_id},
        state=state,
        previous=previous,
        frozen={"split": frozen.get("split"), "nodes": normalized_nodes},
        old_graph_snapshot=_snapshot(data.get("old_graph_snapshot")),
        candidate_graph_snapshot=_snapshot(data.get("candidate_graph_snapshot")),
        candidate_id_mapping=mapping,
        structure_signature={
            "old": _snapshot(signature.get("old")),
            "candidate": _snapshot(signature.get("candidate")),
        },
        version=version,
    )


def save_mainline_reopen(approach_root: Path, data: dict[str, Any]) -> Path:
    """Persist a transaction without replacing a different active transaction."""
    payload = validate_mainline_reopen(data)
    path = mainline_reopen_path(approach_root)
    if path.is_file():
        current = load_mainline_reopen(approach_root)
        if (
            current["transaction_id"] != payload["transaction_id"]
            and current["state"] not in TERMINAL_STATES
        ):
            raise ValueError("cannot replace active mainline-reopen transaction")
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def load_mainline_reopen(approach_root: Path) -> dict[str, Any]:
    """Load the active Main/Split transaction."""
    path = mainline_reopen_path(approach_root)
    if not path.is_file():
        raise FileNotFoundError(f"mainline-reopen not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return validate_mainline_reopen(raw)


def try_load_mainline_reopen(approach_root: Path) -> dict[str, Any] | None:
    """Load a transaction when one exists."""
    path = mainline_reopen_path(approach_root)
    return load_mainline_reopen(approach_root) if path.is_file() else None

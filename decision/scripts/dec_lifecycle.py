#!/usr/bin/env python3
"""Public decision lifecycle helpers for holders (bind / freeze / unfreeze).

Holders must call these instead of importing low-level session-state schema
or writing ``active-session.json`` directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from dec_active_control import _commit_active, _refresh_session_context
from dec_active_session_schema import is_valid_session_root
from dec_domain_constraints_schema import context_docs_map, load_domain_constraints
from dec_gate_control import cmd_init_session
from dec_session_state_schema import (
    set_session_frozen,
    unfreeze_session,
    write_session_state,
)
from dec_session_state_schema import session_state_file

BindMode = Literal["initialize", "existing"]


def _load_resolved_override(resolved_context_path: Path) -> dict[str, Any]:
    path = Path(resolved_context_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"resolved context not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("resolved context must be a JSON object")
    return data


def bind_session(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    session_dir: Path,
    resolved_context_path: Path,
    mode: BindMode,
    constraints_path: Path | None = None,
) -> dict[str, Any]:
    """Bind Active to session_dir after preparing context (context-first)."""
    target = Path(session_dir).resolve()
    override = _load_resolved_override(resolved_context_path)

    if mode == "initialize":
        if is_valid_session_root(target) and (target / "gate-state.json").is_file():
            raise ValueError(
                f"bind_session initialize blocked: gate-state already exists: {target}"
            )
        target.mkdir(parents=True, exist_ok=True)
        rc = cmd_init_session(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
            domain_override=override,
            session_dir=target,
            commit_active=False,
        )
        if rc != 0:
            raise ValueError(f"bind_session initialize failed (cmd_init_session rc={rc})")
        write_session_state(session_state_file(target), "InProgress")
        docs = context_docs_map(load_domain_constraints(target / "domain-constraints.json"))
        active = _commit_active(
            project_root,
            cycle_id,
            stage,
            session_dir=target,
            constraints_path=constraints_path,
        )
        return {
            "ok": True,
            "session_dir": target.as_posix(),
            "active_session": active["active_session"],
            "context_docs": docs,
            "initialized": True,
        }

    if mode != "existing":
        raise ValueError(f"bind_session mode must be initialize|existing, got {mode!r}")

    if not is_valid_session_root(target):
        raise ValueError(
            f"bind_session existing requires valid session root "
            f"(gate-state.json or domain-constraints.json): {target}"
        )
    # Context first, then Active — avoids Active-without-context window.
    docs = _refresh_session_context(target, override)
    active = _commit_active(
        project_root,
        cycle_id,
        stage,
        session_dir=target,
        constraints_path=constraints_path,
    )
    return {
        "ok": True,
        "session_dir": target.as_posix(),
        "active_session": active["active_session"],
        "context_docs": docs,
        "initialized": False,
    }


def freeze_session(session_dir: Path) -> str:
    """Public wrapper: Delivered/InProgress → Frozen. Returns prior state."""
    return set_session_frozen(Path(session_dir).resolve())


def unfreeze_session_public(session_dir: Path) -> bool:
    """Public wrapper: Frozen → InProgress when applicable."""
    return unfreeze_session(Path(session_dir).resolve())

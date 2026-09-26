#!/usr/bin/env python3
"""Execution state: the single step machine of one compose revision.

``execution-state.json`` lives at the revision root next to
``workflow-state.md``; all step artifacts live under ``revision/execution/``.
Session state (Working / ReadyForDelivery / ...) stays in workflow-state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2]
_KERNEL = _SCRIPTS / "_kernel"
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from compose_state_lock import canonical_digest, durable_write_json  # noqa: E402

EXECUTION_DIRNAME = "execution"
EXECUTION_STATE_FILENAME = "execution-state.json"
STATE_VERSION = 1
INITIAL_STATE = "Pending"
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
PRODUCER_STATES = frozenset({"Inductive", "Deductive"})
_ON_DISK_KEYS = frozenset({"version", "state"})


def execution_dir(revision_dir: Path) -> Path:
    """Fixed step-artifact directory of a revision."""
    return (Path(revision_dir).resolve() / EXECUTION_DIRNAME).resolve()


def execution_state_path(revision_dir: Path) -> Path:
    return Path(revision_dir).resolve() / EXECUTION_STATE_FILENAME


def is_revision_root(path: Path) -> bool:
    return execution_state_path(path).is_file()


def working_execution_dir(path: Path) -> Path:
    """Revision root → ``execution/``; any other path is returned unchanged."""
    root = Path(path).resolve()
    if is_revision_root(root):
        return execution_dir(root)
    return root


def build_execution_state(state: str = INITIAL_STATE) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(f"unknown execution state: {state!r}")
    return {"version": STATE_VERSION, "state": state}


def validate_execution_state(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["execution-state must be an object"]
    errors: list[str] = []
    extra = sorted(set(data) - _ON_DISK_KEYS)
    if extra:
        errors.append(f"execution-state has unknown keys: {', '.join(extra)}")
    if data.get("version") != STATE_VERSION:
        errors.append(f"execution-state.version must be {STATE_VERSION}")
    state = data.get("state")
    if state not in STATES:
        errors.append(f"execution-state.state is not a known step state: {state!r}")
    return errors


def _canonical(data: dict[str, Any]) -> dict[str, Any]:
    return {"version": STATE_VERSION, "state": str(data["state"])}


def execution_fingerprint(data: dict[str, Any]) -> str:
    """Stable digest of the step state; changes whenever the step changes."""
    return canonical_digest(_canonical(data))


def save_execution_state(revision_dir: Path, data: dict[str, Any]) -> Path:
    errors = validate_execution_state(data)
    if errors:
        raise ValueError("; ".join(errors))
    path = execution_state_path(revision_dir)
    durable_write_json(path, _canonical(data))
    return path


def load_execution_state(revision_dir: Path) -> dict[str, Any]:
    path = execution_state_path(revision_dir)
    if not path.is_file():
        raise FileNotFoundError(f"execution-state.json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_execution_state(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def current_step(revision_dir: Path) -> str:
    return str(load_execution_state(revision_dir)["state"])


def set_step(revision_dir: Path, state: str) -> dict[str, Any]:
    """Overwrite the step state without transition checks (callers own legality)."""
    data = build_execution_state(state)
    save_execution_state(revision_dir, data)
    return data


def eval_session_phase(revision_dir: Path) -> str:
    """Map the step state onto the Eval session phase vocabulary."""
    state = current_step(revision_dir)
    if state == "Evaluating":
        return "evaluating"
    if state == "Completed":
        return "completed"
    return "pending"


def is_completed(revision_dir: Path) -> bool:
    return current_step(revision_dir) == "Completed"

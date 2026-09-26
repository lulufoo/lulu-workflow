#!/usr/bin/env python3
"""Shared hard-gate checks for deductive-runner confirm exit.

Fails when:
1. ``_facts.json`` is missing
2. ``deductive-pending.json`` is missing (must run ``pending-init``)

Open pending and unreferenced quarantine do not block. Step 3 is display
plus one user confirm.

Design rationale (source repo, why-only):
docs/archive/lulu-workflow/compose/archive-48.0/compose-pending-confirm-display-only-design.md.
"""

from __future__ import annotations

from pathlib import Path

from deductive_pending_schema import pending_path  # noqa: E402
from execution_state_schema import execution_dir  # noqa: E402
from facts_schema import facts_path  # noqa: E402


def evaluate_deductive_gate(revision_dir: Path) -> str | None:
    """Return a failure reason string, or ``None`` when the confirm gate is clear."""
    rev = execution_dir(Path(revision_dir).resolve())
    facts = facts_path(rev)
    if not facts.is_file():
        return f"_facts.json missing (expected {facts.as_posix()})"

    path = pending_path(rev)
    if not path.is_file():
        return (
            f"deductive-pending.json missing (run pending-init; "
            f"expected {path.as_posix()})"
        )
    return None

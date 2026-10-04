"""Resolve this checkout as lulu-workflow, including git worktrees."""

from __future__ import annotations

from pathlib import Path


def workflow_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "scripts" / "cycle_control.py").is_file() and (parent / "eval").is_dir():
            return parent
    raise RuntimeError("lulu-workflow root not found")


def project_root_for_refs() -> Path:
    """Directory used as project_root for ``lulu-workflow/...`` refs."""
    workflow = workflow_root()
    sibling = workflow.parent / "lulu-workflow"
    if sibling.is_dir() and sibling.resolve() == workflow.resolve():
        return workflow.parent
    return workflow


def workflow_ref(ref: str) -> str:
    """Normalize a ``lulu-workflow/...`` ref onto this checkout."""
    prefix = "lulu-workflow/"
    root = project_root_for_refs()
    if root.name != "lulu-workflow" and ref.startswith(prefix):
        return ref[len(prefix) :]
    return ref

#!/usr/bin/env python3
"""Resolve the reference document a work order is split from.

The reference is the Delivered ``lulu-plan`` doc, or the ``lulu-approach``
decision doc when no plan is delivered. Both are located through the cycle's
``delivered-refs.json``; each entry points at a package JSON whose doc path is
relative to the package directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]
for _dir in (
    _WORKFLOW_ROOT / "scripts",
    _WORKFLOW_ROOT / "compose" / "scripts" / "schema" / "session",
):
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))

from compose_package_schema import load_compose_package, package_doc_path  # noqa: E402
from cycle_delivered_refs import load_delivered_refs_file  # noqa: E402

PLAN_SOURCE = "lulu-plan"
APPROACH_SOURCE = "lulu-approach"


def _plan_doc(package_path: Path) -> Path:
    package = load_compose_package(package_path)
    return package_doc_path(package, package_path=package_path)


def _approach_doc(package_path: Path) -> Path:
    if not package_path.is_file():
        raise FileNotFoundError(f"missing decision-package: {package_path}")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    main = data.get("main") if isinstance(data, dict) else None
    rel = Path(str((main or {}).get("decision_doc_path", "")).strip())
    if not rel.parts or rel.is_absolute() or ".." in rel.parts:
        raise ValueError(
            "decision-package.main.decision_doc_path must be a relative path "
            "under the package directory"
        )
    return (package_path.resolve().parent / rel).resolve()


_SOURCES: tuple[tuple[str, Callable[[Path], Path]], ...] = (
    (PLAN_SOURCE, _plan_doc),
    (APPROACH_SOURCE, _approach_doc),
)


def resolve_reference(cycle_id: str, project_root: Path) -> dict[str, str]:
    """Return ``{"source", "tech_ref"}`` for the cycle; plan wins over approach."""
    entries = load_delivered_refs_file(cycle_id, project_root).get("entries") or {}
    for source, doc_of in _SOURCES:
        entry = entries.get(source)
        raw_path = str(entry.get("path", "")).strip() if isinstance(entry, dict) else ""
        if not raw_path:
            continue
        try:
            doc = doc_of(Path(raw_path))
        except (OSError, ValueError) as exc:
            raise ValueError(f"invalid {source} delivery: {exc}") from exc
        if not doc.is_file():
            raise ValueError(f"{source} reference doc not found: {doc}")
        return {"source": source, "tech_ref": str(doc)}
    raise ValueError("missing delivered-refs entry: lulu-plan or lulu-approach")

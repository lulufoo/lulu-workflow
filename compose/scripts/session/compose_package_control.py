#!/usr/bin/env python3
"""Internal Ready-package assemble / validate (not a public CLI).

Called by ``$SESSION_CONTROL ready-for-delivery`` / ``deliver``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
_SESSION = _SCRIPTS / "schema" / "session"
for _p in (_HERE, _SESSION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from compose_package_schema import (  # noqa: E402
    build_compose_package,
    missing_slice_docs,
    save_compose_package,
    validate_committed_package,
    validate_compose_package,
)
from l_ledger_schema import all_completed_unfrozen, load_l_ledger  # noqa: E402
from scope_package_schema import load_scope_package  # noqa: E402
from workflow_paths import load_profile  # noqa: E402


def document_filename_for_profile(profile_id: str) -> str:
    profile = load_profile(profile_id)
    name = str((profile.get("document") or {}).get("filename", "")).strip()
    if not name:
        raise ValueError(f"profile {profile_id!r} missing document.filename")
    return name


def assemble_compose_package(
    revision_dir: Path,
    *,
    profile_id: str,
    require_completed: bool = True,
) -> tuple[Path | None, str | None]:
    """Build and write ``*-package.json`` from the L ledger."""
    rev = Path(revision_dir).resolve()
    try:
        doc_filename = document_filename_for_profile(profile_id)
        ledger = load_l_ledger(rev)
        scope = load_scope_package(rev / "scope-package.json")
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        return None, str(exc)

    if require_completed and not all_completed_unfrozen(ledger):
        return None, "not all L Completed and unfrozen"

    titles = {
        str(row.get("id", "")).strip(): str(row.get("title", "")).strip()
        for row in scope.get("slices") or []
        if isinstance(row, dict)
    }
    slices = [
        {
            "id": nid,
            "title": titles.get(nid, nid) or nid,
            "doc_path": f"{nid}/{doc_filename}",
        }
        for nid in ledger["order"]
    ]
    package = build_compose_package(profile_id=profile_id, slices=slices)
    errors = validate_compose_package(package)
    if errors:
        return None, "; ".join(errors)
    missing = missing_slice_docs(rev, package)
    if missing:
        return None, "missing slice docs: " + ", ".join(missing)
    try:
        path = save_compose_package(rev, doc_filename, package)
    except ValueError as exc:
        return None, str(exc)
    return path, None


def validate_ready_package(
    revision_dir: Path,
    *,
    profile_id: str,
) -> tuple[Path | None, str | None]:
    """Revalidate the committed Ready package. Does not write."""
    rev = Path(revision_dir).resolve()
    try:
        doc_filename = document_filename_for_profile(profile_id)
        ledger = load_l_ledger(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        return None, str(exc)
    if not all_completed_unfrozen(ledger):
        return None, "not all L Completed and unfrozen"
    return validate_committed_package(
        rev,
        doc_filename=doc_filename,
        profile_id=profile_id,
        expected_order=list(ledger["order"]),
    )

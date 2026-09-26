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
    save_compose_package,
    validate_committed_package,
)
from execution_state_schema import EXECUTION_DIRNAME, is_completed  # noqa: E402
from workflow_paths import load_profile  # noqa: E402


def document_filename_for_profile(profile_id: str) -> str:
    profile = load_profile(profile_id)
    name = str((profile.get("document") or {}).get("filename", "")).strip()
    if not name:
        raise ValueError(f"profile {profile_id!r} missing document.filename")
    return name


def package_doc_rel_path(doc_filename: str) -> str:
    return f"{EXECUTION_DIRNAME}/{doc_filename}"


def assemble_compose_package(
    revision_dir: Path,
    *,
    profile_id: str,
    require_completed: bool = True,
) -> tuple[Path | None, str | None]:
    """Build and write ``*-package.json`` pointing at the execution prose."""
    rev = Path(revision_dir).resolve()
    try:
        doc_filename = document_filename_for_profile(profile_id)
        completed = is_completed(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        return None, str(exc)
    if require_completed and not completed:
        return None, "execution is not Completed"
    package = build_compose_package(
        profile_id=profile_id, doc_path=package_doc_rel_path(doc_filename)
    )
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
        completed = is_completed(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        return None, str(exc)
    if not completed:
        return None, "execution is not Completed"
    return validate_committed_package(
        rev,
        doc_filename=doc_filename,
        profile_id=profile_id,
        expected_doc_path=package_doc_rel_path(doc_filename),
    )

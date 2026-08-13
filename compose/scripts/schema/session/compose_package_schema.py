#!/usr/bin/env python3
"""Schema and I/O for revision ``*-package.json`` (compose delivery marker).

Cross-stage delivery entry is this JSON only; per-L prose stays at ``Lx/*-doc.md``.
Shape (v1)::

    {
      "version": 1,
      "profile_id": "lulu-design",
      "slices": [
        {"id": "L1", "title": "...", "doc_path": "L1/design-doc.md"}
      ]
    }

Sequence SSOT is ``slices`` array order. Legacy ``order`` is rejected.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PACKAGE_VERSION = 1
_NODE_ID_RE = re.compile(r"^L\d+$")
_SLICE_KEYS = frozenset({"id", "title", "doc_path"})


def package_filename_from_doc(doc_filename: str) -> str:
    """Derive delivery package name from ``document.filename``.

    ``design-doc.md`` → ``design-package.json``; ``tech-doc.md`` → ``tech-package.json``.
    """
    name = str(doc_filename).strip()
    if not name:
        raise ValueError("doc_filename must be non-empty")
    if name.endswith("-doc.md"):
        return f"{name[: -len('-doc.md')]}-package.json"
    if name.endswith(".md"):
        return f"{name[:-3]}-package.json"
    if name.endswith(".json"):
        return name if name.endswith("-package.json") else f"{name[:-5]}-package.json"
    return f"{name}-package.json"


def compose_package_path(revision_dir: Path, doc_filename: str) -> Path:
    return Path(revision_dir) / package_filename_from_doc(doc_filename)


def build_compose_package(
    *,
    profile_id: str,
    slices: list[dict[str, Any]],
    version: int = PACKAGE_VERSION,
) -> dict[str, Any]:
    """Build a new compose package (F1=A: omit ``order``)."""
    return {
        "version": int(version),
        "profile_id": str(profile_id).strip(),
        "slices": [dict(s) for s in slices],
    }


def validate_compose_package(data: dict[str, Any]) -> list[str]:
    """Validate package shape. ``order`` is forbidden."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["package must be an object"]

    if data.get("version") != PACKAGE_VERSION:
        errors.append(f"version must be {PACKAGE_VERSION}")

    if "order" in data:
        errors.append("order must not be present (sequence is slices array order)")

    profile_id = data.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        errors.append("profile_id must be a non-empty string")

    slices = data.get("slices")
    if not isinstance(slices, list) or not slices:
        errors.append("slices must be a non-empty list")
        return errors

    seen: set[str] = set()
    for idx, slice_row in enumerate(slices):
        where = f"slices[{idx}]"
        if not isinstance(slice_row, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(slice_row) - _SLICE_KEYS
        if extra:
            errors.append(f"{where} unexpected keys: {sorted(extra)}")
        sid = str(slice_row.get("id", "")).strip()
        if not _NODE_ID_RE.match(sid):
            errors.append(f"{where}.id must match L<number>")
        elif sid in seen:
            errors.append(f"slices duplicate id {sid!r}")
        else:
            seen.add(sid)
        if not str(slice_row.get("title", "")).strip():
            errors.append(f"{where}.title must be non-empty")
        doc_path = str(slice_row.get("doc_path", "")).strip()
        if not doc_path or doc_path.startswith("/") or ".." in Path(doc_path).parts:
            errors.append(
                f"{where}.doc_path must be a relative path under the revision root"
            )

    return errors


def missing_slice_docs(revision_dir: Path, package: dict[str, Any]) -> list[str]:
    """Return relative doc_path values whose files are missing under revision_dir."""
    rev = Path(revision_dir)
    missing: list[str] = []
    for slice_row in package.get("slices") or []:
        if not isinstance(slice_row, dict):
            continue
        rel = str(slice_row.get("doc_path", "")).strip()
        if not rel:
            continue
        if not (rev / rel).is_file():
            missing.append(rel)
    return missing


def save_compose_package(revision_dir: Path, doc_filename: str, package: dict[str, Any]) -> Path:
    errors = validate_compose_package(package)
    if errors:
        raise ValueError("; ".join(errors))
    missing = missing_slice_docs(revision_dir, package)
    if missing:
        raise ValueError("missing slice docs: " + ", ".join(missing))
    path = compose_package_path(revision_dir, doc_filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_compose_package(path: Path) -> dict[str, Any]:
    package_path = Path(path)
    if not package_path.is_file():
        raise FileNotFoundError(f"missing compose package: {package_path}")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    errors = validate_compose_package(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def validate_committed_package(
    revision_dir: Path,
    *,
    doc_filename: str,
    profile_id: str,
    expected_order: list[str],
) -> tuple[Path | None, str | None]:
    """Load an existing Ready package and check it against ledger order + docs.

    Does not write or re-assemble.
    """
    rev = Path(revision_dir).resolve()
    path = compose_package_path(rev, doc_filename)
    if not path.is_file():
        return None, "Ready package missing"
    try:
        package = load_compose_package(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if str(package.get("profile_id", "")).strip() != str(profile_id).strip():
        return None, (
            f"package profile_id {package.get('profile_id')!r} != {profile_id!r}"
        )
    order = chain_ids_from_compose_package(package)
    if order != list(expected_order):
        return None, f"package slice order {order!r} != ledger order {list(expected_order)!r}"
    missing = missing_slice_docs(rev, package)
    if missing:
        return None, "missing slice docs: " + ", ".join(missing)
    return path, None


def is_compose_package_path(path: Path | str) -> bool:
    name = Path(path).name
    return name.endswith("-package.json")


def resolve_focus_doc_path(
    package: dict[str, Any],
    focus: str,
    *,
    package_path: Path,
) -> Path:
    """Resolve absolute upstream prose path for ``focus`` from a loaded package."""
    focus_id = str(focus).strip()
    for slice_row in package.get("slices") or []:
        if not isinstance(slice_row, dict):
            continue
        if str(slice_row.get("id", "")).strip() != focus_id:
            continue
        rel = str(slice_row.get("doc_path", "")).strip()
        if not rel:
            raise ValueError(f"package slice {focus_id!r} missing doc_path")
        abs_path = (Path(package_path).resolve().parent / rel).resolve()
        if not abs_path.is_file():
            raise FileNotFoundError(f"upstream doc not found for {focus_id}: {abs_path}")
        return abs_path
    raise ValueError(f"focus {focus_id!r} not found in package slices")


def chain_ids_from_compose_package(package: dict[str, Any]) -> list[str]:
    """Return L* ids in slices array order."""
    return [
        str(row["id"]).strip()
        for row in package.get("slices") or []
        if isinstance(row, dict) and str(row.get("id", "")).strip()
    ]

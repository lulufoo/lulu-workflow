#!/usr/bin/env python3
"""Schema and I/O for per-section inductive maturity ledger (K4 slim).

Design rationale (source repo, why-only):
docs/domain/archive/compose/archive-2.0/compose-fact-first-k4-fact-native-design.md §4.2;
docs/domain/ssot/compose/inductive-ssot/compose-inductive-architecture.md.

Section files are maturity-only: ``key`` / ``status`` / ``frontier_kw``.
Opens live in ``inductive-opens.json``; facts in ``_facts.json``.
AI never hand-writes these files — only scripts via this module (I12).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECTION_STATUSES = frozenset({"untouched", "active", "cleared", "skipped"})

_INDEX_REQUIRED = ("version", "cycle_id")
_SECTION_REQUIRED = ("key", "status", "frontier_kw")


def section_dir(out_dir: Path) -> Path:
    return Path(out_dir) / "inductive-scope"


def section_path(out_dir: Path, key: str) -> Path:
    return section_dir(out_dir) / f"{key}.json"


def index_path(out_dir: Path) -> Path:
    return section_dir(out_dir) / "_index.json"


def validate_section(doc: dict[str, Any]) -> list[str]:
    """Return validation errors for a maturity section document (empty = valid)."""
    errors: list[str] = []

    if "key" not in doc or not str(doc.get("key", "")).strip():
        errors.append("section: missing required field 'key'")

    status = str(doc.get("status", "")).lower()
    if "status" not in doc:
        errors.append("section: missing required field 'status'")
    elif status not in SECTION_STATUSES:
        errors.append(f"section: invalid status {status!r}")

    if "frontier_kw" not in doc:
        errors.append("section: missing required field 'frontier_kw'")
    else:
        fk = doc["frontier_kw"]
        if not isinstance(fk, int) or fk < 0 or fk > 4:
            errors.append(f"section: frontier_kw must be int 0..4, got {fk!r}")

    extra = set(doc) - set(_SECTION_REQUIRED)
    if extra:
        errors.append(f"section: unexpected fields {sorted(extra)}")

    return errors


def validate_index(doc: dict[str, Any]) -> list[str]:
    """Return validation errors for _index.json (empty = valid)."""
    errors: list[str] = []
    for field in _INDEX_REQUIRED:
        if field not in doc or doc[field] in (None, ""):
            errors.append(f"index: missing required field {field!r}")
    if "version" in doc and str(doc["version"]) not in {"1"}:
        errors.append(f"index: unsupported version {doc.get('version')!r}")
    if "last_checkpoint" in doc and doc["last_checkpoint"] is not None:
        if not isinstance(doc["last_checkpoint"], str):
            errors.append("index: last_checkpoint must be a string or null")
    return errors


def empty_section(key: str, status: str = "untouched", frontier_kw: int = 0) -> dict[str, Any]:
    return {
        "key": key,
        "status": status,
        "frontier_kw": frontier_kw,
    }


def list_section_keys(out_dir: Path) -> list[str]:
    """Return section keys that have a JSON file on disk (excluding _index)."""
    d = section_dir(out_dir)
    if not d.exists():
        return []
    return sorted(
        p.stem for p in d.glob("*.json") if p.name != "_index.json"
    )


def load_section(out_dir: Path, key: str) -> dict[str, Any]:
    path = section_path(out_dir, key)
    if not path.exists():
        raise FileNotFoundError(f"section file not found: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = validate_section(doc)
    if errs:
        raise ValueError(f"invalid section {key}: " + "; ".join(errs))
    return doc


def save_section(out_dir: Path, doc: dict[str, Any]) -> Path:
    errs = validate_section(doc)
    if errs:
        raise ValueError("invalid section: " + "; ".join(errs))
    path = section_path(out_dir, str(doc["key"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_index(out_dir: Path) -> dict[str, Any]:
    path = index_path(out_dir)
    if not path.exists():
        raise FileNotFoundError(f"index file not found: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = validate_index(doc)
    if errs:
        raise ValueError("invalid index: " + "; ".join(errs))
    return doc


def save_index(out_dir: Path, doc: dict[str, Any]) -> Path:
    errs = validate_index(doc)
    if errs:
        raise ValueError("invalid index: " + "; ".join(errs))
    path = index_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def ensure_section(out_dir: Path, key: str) -> dict[str, Any]:
    """Load section or create an empty untouched document on disk."""
    path = section_path(out_dir, key)
    if path.exists():
        return load_section(out_dir, key)
    doc = empty_section(key)
    save_section(out_dir, doc)
    return doc

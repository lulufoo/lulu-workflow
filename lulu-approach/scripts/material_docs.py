"""Resolve Context / Constraint material file lists for lulu-approach.

Uses the same ``build_context_loading`` discovery as binding ``context.docs``,
then filters by a script-owned key table. Binding map must not include these
keys (stripped in ``resolve_context``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

_SKILL_DIR = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SKILL_DIR.parent
_SCRIPTS = _WORKFLOW_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_APPROACH_SCRIPTS = _SKILL_DIR / "scripts"
if str(_APPROACH_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_APPROACH_SCRIPTS))
_DECISION_SCRIPTS = _WORKFLOW_ROOT / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from context_loading import build_context_loading  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402

from dec_domain_constraints_schema import load_constraints_config  # noqa: E402

STAGE = "lulu-approach"

# Keys removed from binding context.docs (Main and Dx).
BINDING_EXCLUDED_KEYS: frozenset[str] = frozenset({"product_spec", "tech_arch"})

# Script-owned kind → docs keys (extend here for future Constraint instances).
_KIND_KEYS: dict[str, tuple[str, ...]] = {
    "context": ("product_spec", "product_blueprint"),
    "constraint": ("tech_arch",),
}


def strip_binding_excluded(docs: dict[str, str]) -> dict[str, str]:
    """Drop material keys that must not appear on the binding map."""
    return {k: v for k, v in docs.items() if k not in BINDING_EXCLUDED_KEYS}


def resolve_material_files(
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    kind: str,
) -> list[str]:
    """Return absolute paths for ``kind`` (``context`` | ``constraint``)."""
    key = kind.strip().lower()
    if key not in _KIND_KEYS:
        raise ValueError(f"unknown material kind: {kind!r}")
    load_constraints_config(constraints_path)
    cache_dir = project_root / platform_cache_dir(detect_platform())
    docs = dict(
        (build_context_loading(cycle_id, STAGE, cache_dir=cache_dir).get("docs") or {})
    )
    files: list[str] = []
    for doc_key in _KIND_KEYS[key]:
        path = docs.get(doc_key)
        if path:
            files.append(str(Path(path).resolve()))
    return files


def files_payload(files: Iterable[str]) -> dict[str, list[str]]:
    return {"files": list(files)}


__all__ = [
    "BINDING_EXCLUDED_KEYS",
    "files_payload",
    "resolve_material_files",
    "strip_binding_excluded",
]

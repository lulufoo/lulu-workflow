#!/usr/bin/env python3
"""Compose-owned common Eval dimensions: bind, skip, and merge."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from delivered_refs_schema import DeliveredRef  # noqa: E402
from resolved_refs_schema import StrictResolvedRefs  # noqa: E402
from scope_package_schema import (  # noqa: E402
    is_scope_package_path,
    load_scope_package,
    scope_source_path,
)

COMMON_DIMENSION_IDS: tuple[str, ...] = (
    "intent-fidelity",
    "scope-continuity",
    "norm-conformance",
)
SKIP_EMPTY_INTENT = "empty_intent_baseline_refs"
SKIP_EMPTY_NORM = "empty_norm_constraint_refs"

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_DEFS_DIR = _WORKFLOW_ROOT / "compose" / "eval" / "dimension-defs"


class ComposeCommonEvalError(ValueError):
    """Common-dimension bind or merge failed."""


def load_common_dimension_def(dim_id: str) -> dict[str, Any]:
    if dim_id not in COMMON_DIMENSION_IDS:
        raise ComposeCommonEvalError(f"unknown common dimension: {dim_id!r}")
    path = _DEFS_DIR / f"{dim_id}.json"
    if not path.is_file():
        raise ComposeCommonEvalError(f"missing common dimension def: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or str(data.get("id") or "") != dim_id:
        raise ComposeCommonEvalError(f"invalid common dimension def: {path}")
    return copy.deepcopy(data)


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_sot_file(
    raw: str,
    *,
    project_root: Path,
    extra_roots: list[Path] | None = None,
) -> Path:
    text = str(raw).strip()
    if not text:
        raise ComposeCommonEvalError("SoT path is empty")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = Path(project_root) / candidate
    if candidate.is_symlink():
        raise ComposeCommonEvalError(f"SoT path must not be a symlink: {candidate}")
    if not candidate.is_file():
        raise ComposeCommonEvalError(f"SoT path missing or unreadable: {candidate}")
    resolved = candidate.resolve()
    allowed = [Path(project_root).resolve()]
    allowed.extend(Path(root).resolve() for root in (extra_roots or []))
    if not any(_contained(resolved, root) for root in allowed):
        raise ComposeCommonEvalError(f"SoT path escapes allowed roots: {resolved}")
    return resolved


def resolve_scope_continuity_sot(
    *,
    project_root: Path,
    scope_ref: DeliveredRef | None,
    extra_roots: list[Path] | None = None,
) -> Path:
    """Resolve the single readable parent document for Scope Continuity."""
    if scope_ref is None or not str(scope_ref.path).strip():
        raise ComposeCommonEvalError("scope_ref missing")
    roots = list(extra_roots or [])
    if _WORKFLOW_ROOT not in roots:
        roots.append(_WORKFLOW_ROOT)
    raw = Path(scope_ref.path)
    if not raw.is_absolute():
        raw = Path(project_root) / raw
    if is_scope_package_path(raw):
        try:
            package = load_scope_package(raw)
        except (FileNotFoundError, ValueError, OSError) as exc:
            raise ComposeCommonEvalError(f"scope-package unreadable: {exc}") from exc
        source = scope_source_path(package, project_root=project_root)
        return resolve_sot_file(str(source), project_root=project_root, extra_roots=roots)
    return resolve_sot_file(str(raw), project_root=project_root, extra_roots=roots)


def _sots_from_refs(
    refs: list[DeliveredRef],
    *,
    project_root: Path,
    extra_roots: list[Path],
) -> list[dict[str, str]]:
    sots: list[dict[str, str]] = []
    for ref in refs:
        path = resolve_sot_file(ref.path, project_root=project_root, extra_roots=extra_roots)
        sots.append({"ref": path.as_posix()})
    return sots


def compose_common_dimensions(
    refs: StrictResolvedRefs,
    *,
    parent_sot: Path,
    project_root: Path,
    extra_roots: list[Path] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return Common Dimensions in Intent → Scope → Norm order plus skip reasons."""
    roots = list(extra_roots or [])
    if _WORKFLOW_ROOT not in roots:
        roots.append(_WORKFLOW_ROOT)
    skip_reasons: dict[str, str] = {}
    intent = load_common_dimension_def("intent-fidelity")
    if refs.intent_baseline_refs:
        intent["sots"] = _sots_from_refs(
            refs.intent_baseline_refs,
            project_root=project_root,
            extra_roots=roots,
        )
    else:
        intent["sots"] = []
        skip_reasons["intent-fidelity"] = SKIP_EMPTY_INTENT
    scope = load_common_dimension_def("scope-continuity")
    scope["sots"] = [{"ref": Path(parent_sot).as_posix()}]
    norm = load_common_dimension_def("norm-conformance")
    if refs.norm_constraint_refs:
        norm["sots"] = _sots_from_refs(
            refs.norm_constraint_refs,
            project_root=project_root,
            extra_roots=roots,
        )
    else:
        norm["sots"] = []
        skip_reasons["norm-conformance"] = SKIP_EMPTY_NORM
    return [intent, scope, norm], skip_reasons


def assert_one_symbol_namespace(dimensions: list[dict[str, Any]]) -> None:
    """Fail when any id or legacy_alias collides in one symbol namespace."""
    seen: dict[str, str] = {}
    for index, dimension in enumerate(dimensions):
        if not isinstance(dimension, dict):
            raise ComposeCommonEvalError(f"dimensions[{index}] must be an object")
        dim_id = str(dimension.get("id") or "").strip()
        alias = str(dimension.get("legacy_alias") or "").strip()
        for symbol, kind in ((dim_id, "id"), (alias, "alias")):
            if not symbol:
                continue
            prior = seen.get(symbol)
            if prior is not None:
                raise ComposeCommonEvalError(
                    f"dimension symbol collision: {symbol!r} used as {prior} and {kind}"
                )
            seen[symbol] = kind


def merge_common_and_stage(
    common: list[dict[str, Any]],
    stage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prepend Common Dimensions; reject Stage overwrite of Common symbols."""
    for index, dimension in enumerate(stage):
        if not isinstance(dimension, dict):
            raise ComposeCommonEvalError(f"stage dimensions[{index}] must be an object")
        dim_id = str(dimension.get("id") or "").strip()
        alias = str(dimension.get("legacy_alias") or "").strip()
        if dim_id in COMMON_DIMENSION_IDS or alias in COMMON_DIMENSION_IDS:
            raise ComposeCommonEvalError(
                f"stage contribution must not include common dimension {dim_id or alias!r}"
            )
    merged = [copy.deepcopy(item) for item in common]
    merged.extend(copy.deepcopy(item) for item in stage)
    assert_one_symbol_namespace(merged)
    return merged

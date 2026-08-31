#!/usr/bin/env python3
"""Project upstream delivery packages → ``scope-package.json``.

Shared by lulu-design and lulu-plan StartAdapters (archive-1.0 P3 / archive-2.0).

D1: empty decision slices → single ``L1`` from ``main.decision_doc_path``.
D2: norm ``kind`` closed set (validated here when building norm refs).
D3: write once under the caller revision dir; refuse same-rev overwrite.

Design rationale: docs/domain/archive/decision/
decision-fact-retire-doc-ssot-design.md
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_START_DIR = Path(__file__).resolve().parent
_SCRIPTS = _START_DIR.parent
_WORKFLOW_ROOT = _SCRIPTS.parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

# Load approach schema by file path — do NOT put approach schema/ on sys.path
# (it would shadow compose dependency_tree_schema / similar names).
_DP_PATH = (
    _WORKFLOW_ROOT
    / "lulu-approach"
    / "scripts"
    / "schema"
    / "decision_package_schema.py"
)
_dp_spec = importlib.util.spec_from_file_location(
    "_shared_decision_package_schema",
    _DP_PATH,
)
if _dp_spec is None or _dp_spec.loader is None:
    raise ImportError(f"cannot load decision_package_schema: {_DP_PATH}")
_dp_mod = importlib.util.module_from_spec(_dp_spec)
_dp_spec.loader.exec_module(_dp_mod)
DECISION_PACKAGE_FILENAME = _dp_mod.DECISION_PACKAGE_FILENAME
is_decision_package_path = _dp_mod.is_decision_package_path
load_decision_package = _dp_mod.load_decision_package

from delivered_refs_schema import DeliveredRef  # noqa: E402
from compose_package_schema import load_compose_package  # noqa: E402
from scope_package_schema import (  # noqa: E402
    SCOPE_PACKAGE_FILENAME,
    build_scope_package,
    save_scope_package,
)

DECISION_PACKAGE_ARTIFACT = "decision-package"
NORM_KINDS = frozenset(
    {"parent_decision", "split_artifact", "topic_arch", "other"}
)
_DEPENDENCY_TREE = "dependency-tree.json"
_DECISION_RULERS = "decision-rulers.json"


class ScopePackageProjectionError(ValueError):
    """decision-package → scope-package projection failed."""


def is_decision_package_ref(ref: DeliveredRef) -> bool:
    """True when delivered ref is an approach decision-package (artifact or path)."""
    if str(ref.artifact or "").strip() == DECISION_PACKAGE_ARTIFACT:
        return True
    return is_decision_package_path(ref.path)


def reject_decision_package_as_scope(path: Path | str) -> None:
    """Hard-reject using ``decision-package.json`` as ``$SCOPE_REF``."""
    if is_decision_package_path(path):
        raise ScopePackageProjectionError(
            "decision-package.json must not be used as $SCOPE_REF; "
            "project to scope-package.json first"
        )


def _resolve_source_path(package_root: Path, rel: str) -> str:
    text = str(rel).strip()
    if not text:
        raise ScopePackageProjectionError("source path must be non-empty")
    path = (package_root / text).resolve()
    if not path.is_file():
        raise ScopePackageProjectionError(f"source path not found: {path}")
    return str(path)


def project_decision_package_to_scope_slices(
    package: dict[str, Any],
    *,
    approach_root: Path,
) -> list[dict[str, Any]]:
    """Map decision-package → ordered scope-package slices (L1…Ln).

    Empty ``slices`` (no-split): one ``L1`` from ``main.decision_doc_path``.
    Non-empty: ``L1…Ln`` from package slices in array order; ``main`` excluded.
    """
    root = Path(approach_root).resolve()
    raw_slices = package.get("slices")
    if not isinstance(raw_slices, list):
        raise ScopePackageProjectionError("decision-package.slices must be a list")

    main = package.get("main")
    if not isinstance(main, dict):
        raise ScopePackageProjectionError("decision-package.main must be an object")

    if not raw_slices:
        source_path = _resolve_source_path(
            root, str(main.get("decision_doc_path", ""))
        )
        return [
            {
                "id": "L1",
                "title": "main",
                "source_path": source_path,
                "source_id": "main",
            }
        ]

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_slices):
        if not isinstance(row, dict):
            raise ScopePackageProjectionError(f"slices[{idx}] must be an object")
        source_id = str(row.get("id", "")).strip()
        title = str(row.get("title", "")).strip()
        source_path = _resolve_source_path(
            root, str(row.get("decision_doc_path", ""))
        )
        if not source_id or not title:
            raise ScopePackageProjectionError(
                f"slices[{idx}] requires non-empty id and title"
            )
        out.append(
            {
                "id": f"L{idx + 1}",
                "title": title,
                "source_path": source_path,
                "source_id": source_id,
            }
        )
    return out


def write_scope_package_projection(
    *,
    decision_package_path: Path,
    output_dir: Path | None = None,
    revision_dir: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Load decision-package, project, write ``scope-package.json``."""
    pkg_path = Path(decision_package_path).resolve()
    if not is_decision_package_path(pkg_path):
        raise ScopePackageProjectionError(
            f"expected {DECISION_PACKAGE_FILENAME}, got {pkg_path.name!r}"
        )
    package = load_decision_package(pkg_path)
    slices = project_decision_package_to_scope_slices(
        package,
        approach_root=pkg_path.parent,
    )
    return materialize_scope_package(
        slices=slices,
        output_dir=output_dir,
        revision_dir=revision_dir,
        overwrite=overwrite,
    )


def project_compose_package_to_scope_slices(
    package: dict[str, Any],
    *,
    package_root: Path,
) -> list[dict[str, Any]]:
    """Map a compose delivery package's prose slices to scope source slices."""
    root = Path(package_root).resolve()
    raw_slices = package.get("slices")
    if not isinstance(raw_slices, list) or not raw_slices:
        raise ScopePackageProjectionError("compose package.slices must be non-empty")

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_slices):
        if not isinstance(row, dict):
            raise ScopePackageProjectionError(f"slices[{idx}] must be an object")
        source_id = str(row.get("id", "")).strip()
        title = str(row.get("title", "")).strip()
        source_path = _resolve_source_path(root, str(row.get("doc_path", "")))
        if not source_id or not title:
            raise ScopePackageProjectionError(
                f"slices[{idx}] requires non-empty id and title"
            )
        out.append(
            {
                "id": f"L{idx + 1}",
                "title": title,
                "source_path": source_path,
                "source_id": source_id,
            }
        )
    return out


def write_compose_package_scope_projection(
    *,
    compose_package_path: Path,
    output_dir: Path | None = None,
    revision_dir: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Project a compose delivery package to a scope package."""
    pkg_path = Path(compose_package_path).resolve()
    package = load_compose_package(pkg_path)
    slices = project_compose_package_to_scope_slices(
        package,
        package_root=pkg_path.parent,
    )
    return materialize_scope_package(
        slices=slices,
        output_dir=output_dir,
        revision_dir=revision_dir,
        overwrite=overwrite,
    )


def materialize_scope_package(
    *,
    slices: list[dict[str, Any]],
    output_dir: Path | None = None,
    revision_dir: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Write a previously validated scope projection.

    ``revision_dir`` is an alias of ``output_dir`` (holder preflight writes
    outside any revision).
    """
    dest = Path(output_dir or revision_dir or "").resolve()
    if not dest.as_posix():
        raise ScopePackageProjectionError("output_dir required")
    existing = dest / SCOPE_PACKAGE_FILENAME
    if existing.is_file() and not overwrite:
        raise ScopePackageProjectionError(
            "scope-package.json already exists; no same-dir rebuild (D3)"
        )
    return save_scope_package(dest, build_scope_package(slices))


def make_norm_ref(
    *,
    delivered_type: str,
    path: str,
    kind: str,
) -> DeliveredRef:
    """Build a norm-channel DeliveredRef with required closed-set ``kind`` (D2)."""
    k = str(kind).strip()
    if k not in NORM_KINDS:
        raise ScopePackageProjectionError(
            f"norm kind must be one of {sorted(NORM_KINDS)}, got {kind!r}"
        )
    p = str(path).strip()
    if not p:
        raise ScopePackageProjectionError("norm ref path must be non-empty")
    return DeliveredRef(type=delivered_type, path=p, kind=k)


def norm_refs_from_decision_package(
    *,
    decision_package_path: Path,
    package: dict[str, Any] | None = None,
) -> list[DeliveredRef]:
    """Norm channel: main decision-doc + optional split tree/rulers, each with ``kind``."""
    pkg_path = Path(decision_package_path).resolve()
    root = pkg_path.parent
    data = package if package is not None else load_decision_package(pkg_path)
    main = data.get("main")
    if not isinstance(main, dict):
        raise ScopePackageProjectionError("decision-package.main must be an object")

    refs: list[DeliveredRef] = []
    doc_rel = str(main.get("decision_doc_path", "")).strip()
    if doc_rel:
        doc_abs = str((root / doc_rel).resolve())
        if Path(doc_abs).is_file():
            refs.append(
                make_norm_ref(
                    delivered_type="lulu-approach",
                    path=doc_abs,
                    kind="parent_decision",
                )
            )

    for name in (_DEPENDENCY_TREE, _DECISION_RULERS):
        split_path = root / name
        if split_path.is_file():
            refs.append(
                make_norm_ref(
                    delivered_type="lulu-approach",
                    path=str(split_path.resolve()),
                    kind="split_artifact",
                )
            )
    return refs

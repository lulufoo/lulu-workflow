#!/usr/bin/env python3
"""Write ``scope-package.json`` from one upstream source document.

Holder StartAdapters resolve their upstream artifact to a single document and
call ``write_scope_package_from_source``; compose never reads upstream package
shapes. A compose delivery package (``*-package.json``) is the one upstream
shape compose owns, so it is projected here as well.
"""

from __future__ import annotations

import sys
from pathlib import Path

_START_DIR = Path(__file__).resolve().parent
_SCRIPTS = _START_DIR.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_package_schema import load_compose_package, package_doc_path  # noqa: E402
from delivered_refs_schema import DeliveredRef  # noqa: E402
from scope_package_schema import (  # noqa: E402
    SCOPE_PACKAGE_FILENAME,
    build_scope_package,
    is_scope_package_path,
    save_scope_package,
)

NORM_KINDS = frozenset({"topic_arch", "other"})


class ScopePackageProjectionError(ValueError):
    """Upstream artifact → scope-package projection failed."""


def reject_non_scope_package(path: Path | str) -> None:
    """``$SCOPE_REF`` must be the projected scope-package, never an upstream package."""
    if not is_scope_package_path(path):
        raise ScopePackageProjectionError(
            f"$SCOPE_REF must be {SCOPE_PACKAGE_FILENAME}, got {Path(str(path)).name!r}"
        )


def write_scope_package_from_source(
    *,
    source_path: Path,
    output_dir: Path,
    title: str | None = None,
    source_id: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Write ``scope-package.json`` for one existing source document."""
    source = Path(source_path).resolve()
    if not source.is_file():
        raise ScopePackageProjectionError(f"source path not found: {source}")
    dest = Path(output_dir).resolve()
    existing = dest / SCOPE_PACKAGE_FILENAME
    if existing.is_file() and not overwrite:
        raise ScopePackageProjectionError(
            "scope-package.json already exists; no same-dir rebuild"
        )
    package = build_scope_package(
        source_path=str(source), source_id=source_id, title=title
    )
    return save_scope_package(dest, package)


def write_compose_package_scope_projection(
    *,
    compose_package_path: Path,
    output_dir: Path,
    overwrite: bool = False,
) -> Path:
    """Project a compose delivery package (``doc_path``) to a scope package."""
    pkg_path = Path(compose_package_path).resolve()
    package = load_compose_package(pkg_path)
    return write_scope_package_from_source(
        source_path=package_doc_path(package, package_path=pkg_path),
        output_dir=output_dir,
        title=str(package.get("profile_id") or ""),
        source_id=str(package.get("profile_id") or ""),
        overwrite=overwrite,
    )


def make_norm_ref(*, delivered_type: str, path: str, kind: str) -> DeliveredRef:
    """Build a norm-channel DeliveredRef with a closed-set ``kind``."""
    k = str(kind).strip()
    if k not in NORM_KINDS:
        raise ScopePackageProjectionError(
            f"norm kind must be one of {sorted(NORM_KINDS)}, got {kind!r}"
        )
    p = str(path).strip()
    if not p:
        raise ScopePackageProjectionError("norm ref path must be non-empty")
    return DeliveredRef(type=delivered_type, path=p, kind=k)

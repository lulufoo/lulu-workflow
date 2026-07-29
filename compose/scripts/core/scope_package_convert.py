#!/usr/bin/env python3
"""P4.convert control: scope-package → locked chain tree + per-L fact_path mirrors.

C1=A: run once at compose start / Initializing (no rebuild-convert CLI).
C2=A: strict chain from slices array order (no package ``order`` field).
C3=B: mirror ``fact_path`` into ``Lx/scope-ref.json`` (no fact file copy).
C5=A: refuse overwrite when tree already locked — open a new revision.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
_SESSION = _SCRIPTS / "schema" / "session"
_SECTION = _SCRIPTS / "section"
for _p in (_HERE, _SESSION, _SECTION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dependency_tree_schema import (  # noqa: E402
    dependency_tree_path,
    load_dependency_tree,
    save_dependency_tree,
    validate_dependency_tree,
)
from discussion_pointer_schema import (  # noqa: E402
    build_pointer_from_tree,
    save_discussion_pointer,
)
from facts_schema import FACTS_BASENAME  # noqa: E402
from resolved_refs_schema import (  # noqa: E402
    has_resolved_refs,
    resolved_scope_ref,
)
from scope_package_schema import (  # noqa: E402
    SCOPE_PACKAGE_FILENAME,
    chain_dependency_tree_from_scope_package,
    chain_ids_from_scope_package,
    is_scope_package_path,
    load_scope_package,
    load_scope_ref_mirror,
    scope_ref_mirror_path,
    stub_slice_rulers_from_scope_package,
    write_fact_path_mirrors,
)
from slice_rulers_schema import (  # noqa: E402
    save_slice_rulers,
    validate_slice_rulers,
)

_SLICE_MUTATION_BLOCK = (
    "scope-package convert froze the L set; mutating slices/topology is forbidden "
    "(start a new compose revision)"
)


class ScopePackageConvertError(ValueError):
    """scope-package convert failed or refused (C5)."""


def revision_uses_scope_package(revision_dir: Path) -> bool:
    """True when this revision's primary scope is / holds a scope-package."""
    rev = Path(revision_dir).resolve()
    if (rev / SCOPE_PACKAGE_FILENAME).is_file():
        return True
    if has_resolved_refs(rev):
        ref = resolved_scope_ref(rev)
        if ref is not None and is_scope_package_path(ref.path):
            return True
    return False


def slice_mutation_block_reason(revision_dir: Path) -> str | None:
    """Return hard-reject message when slice-mutation commands must be blocked."""
    if revision_uses_scope_package(revision_dir):
        return _SLICE_MUTATION_BLOCK
    return None


def _mirrors_match_package(revision_dir: Path, package: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for row in package.get("slices") or []:
        if not isinstance(row, dict):
            continue
        nid = str(row.get("id", "")).strip()
        expected = str(row.get("fact_path", "")).strip()
        if not nid:
            continue
        try:
            mirror = load_scope_ref_mirror(revision_dir, nid)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{nid}: {exc}")
            continue
        actual = str(mirror.get("fact_path", "")).strip()
        if actual != expected:
            errors.append(
                f"{nid}: fact_path mirror {actual!r} != scope-package {expected!r}"
            )
    return errors


def _tree_already_locked(revision_dir: Path) -> bool:
    path = dependency_tree_path(revision_dir)
    if not path.is_file():
        return False
    try:
        tree = load_dependency_tree(revision_dir)
    except (ValueError, json.JSONDecodeError, FileNotFoundError):
        return False
    return tree.get("status") == "locked"


def _lock_chain_tree(
    revision_dir: Path,
    *,
    tree: dict[str, Any],
    rulers: dict[str, Any] | None,
) -> None:
    rev = Path(revision_dir).resolve()
    root_facts = rev / FACTS_BASENAME
    if root_facts.is_file():
        raise ScopePackageConvertError(
            f"root {FACTS_BASENAME} present; migrate to L1/ or remove before convert "
            f"(path={root_facts.as_posix()})"
        )

    locked = dict(tree)
    locked.setdefault("version", 1)
    locked["status"] = "locked"
    errors = validate_dependency_tree(locked)
    if errors:
        raise ScopePackageConvertError("; ".join(errors))

    node_ids = [str(n["id"]) for n in locked["nodes"]]
    rulers_payload: dict[str, Any] | None = None
    if len(node_ids) >= 2:
        if rulers is None:
            raise ScopePackageConvertError(
                "multi-L scope-package convert requires slice rulers"
            )
        rulers_payload = dict(rulers)
        rulers_payload.setdefault("version", 1)
        rulers_payload["status"] = "locked"
        r_errors = validate_slice_rulers(
            rulers_payload, required_node_ids=node_ids
        )
        if r_errors:
            raise ScopePackageConvertError("; ".join(r_errors))

    save_dependency_tree(rev, locked)
    pointer = build_pointer_from_tree(locked)
    save_discussion_pointer(rev, pointer, tree=locked)
    for node in locked["nodes"]:
        (rev / str(node["id"])).mkdir(parents=True, exist_ok=True)
    if rulers_payload is not None:
        save_slice_rulers(rev, rulers_payload)


def convert_scope_package(
    revision_dir: Path,
    *,
    scope_package_path: Path,
) -> dict[str, Any]:
    """Hard-convert once: lock chain tree + pointer + Lx/ + fact_path mirrors.

    Raises ``ScopePackageConvertError`` when the tree is already locked (C5)
    or the package path is not a scope-package.
    """
    rev = Path(revision_dir).resolve()
    pkg_path = Path(scope_package_path).resolve()
    if not is_scope_package_path(pkg_path):
        raise ScopePackageConvertError(
            f"expected {SCOPE_PACKAGE_FILENAME}, got {pkg_path.name!r}"
        )
    if _tree_already_locked(rev):
        raise ScopePackageConvertError(
            "dependency tree already locked; scope-package convert refuses "
            "overwrite (start a new compose revision)"
        )

    package = load_scope_package(pkg_path)
    tree = chain_dependency_tree_from_scope_package(package)
    rulers = stub_slice_rulers_from_scope_package(package)
    _lock_chain_tree(rev, tree=tree, rulers=rulers)
    mirrors = write_fact_path_mirrors(rev, package)
    order = chain_ids_from_scope_package(package)
    return {
        "ok": True,
        "command": "convert-scope-package",
        "scope_package_path": pkg_path.as_posix(),
        "node_ids": order,
        "mirror_paths": [p.as_posix() for p in mirrors],
        "multi_l": len(order) >= 2,
    }


def ensure_scope_package_convert(
    revision_dir: Path,
    *,
    scope_package_path: Path | None = None,
) -> dict[str, Any]:
    """Run convert once when needed; verify mirrors if already locked (C1/C5).

    * Tree locked + mirrors match → noop success.
    * Tree locked + mirrors missing/mismatch → error (new revision).
    * Tree not locked → convert once.
    """
    rev = Path(revision_dir).resolve()
    pkg_path: Path | None
    if scope_package_path is not None:
        pkg_path = Path(scope_package_path).resolve()
    elif (rev / SCOPE_PACKAGE_FILENAME).is_file():
        pkg_path = rev / SCOPE_PACKAGE_FILENAME
    elif has_resolved_refs(rev):
        ref = resolved_scope_ref(rev)
        if ref is not None and is_scope_package_path(ref.path):
            pkg_path = Path(ref.path).resolve()
        else:
            pkg_path = None
    else:
        pkg_path = None

    if pkg_path is None or not is_scope_package_path(pkg_path):
        return {"ok": True, "skipped": True, "reason": "scope is not scope-package"}

    package = load_scope_package(pkg_path)
    if _tree_already_locked(rev):
        mismatches = _mirrors_match_package(rev, package)
        if mismatches:
            raise ScopePackageConvertError(
                "scope-package convert artifacts incomplete or drifted; "
                "start a new compose revision: " + "; ".join(mismatches)
            )
        order = chain_ids_from_scope_package(package)
        return {
            "ok": True,
            "noop": True,
            "command": "convert-scope-package",
            "scope_package_path": pkg_path.as_posix(),
            "node_ids": order,
            "mirror_paths": [
                scope_ref_mirror_path(rev, nid).as_posix() for nid in order
            ],
            "multi_l": len(order) >= 2,
        }
    return convert_scope_package(rev, scope_package_path=pkg_path)

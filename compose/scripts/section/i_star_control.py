#!/usr/bin/env python3
"""Unified I* resolve for compose Initializing (``resolve-i-star``).

Key off profile ``drafting.inductive`` (mutually exclusive sources):
  false → ``_partition.json`` filtered by home
  true  → inductive-scope ``{SECTION}.json`` decisions[].text

Design SSOT: docs/biz/compose-section-partition-design.md §6 (I* resolve).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
_SCOPE = _SCRIPTS / "scope"
for _p in (_SCRIPTS, _SCOPE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from partition_schema import (  # noqa: E402
    filter_i_star,
    load_partition,
    partition_path,
)
from scope_resolver import resolve_inductive_fidelity  # noqa: E402
from workflow_paths import load_profile  # noqa: E402


def drafting_inductive(profile_id: str, project_root: Path) -> bool:
    profile = load_profile(profile_id, project_root=project_root)
    return (profile.get("drafting") or {}).get("inductive") is True


def resolve_i_star_text(
    *,
    revision_dir: Path,
    section: str,
    profile_id: str,
    project_root: Path,
    inductive_dir: Path | None = None,
) -> tuple[str, str | None]:
    """Return ``(i_star_prose, error)``. error set ⇒ caller should exit non-zero.

    Empty prose with error=None is success (section has no atoms / decisions).
    """
    key = section.strip().upper()
    if not key:
        return "", "section key is required"

    root = project_root.resolve()
    rev = revision_dir.resolve()
    inductive = drafting_inductive(profile_id.strip(), root)

    if inductive:
        indir = inductive_dir.resolve() if inductive_dir is not None else None
        if indir is None or not indir.is_dir():
            return "", (
                "drafting.inductive is true but inductive-dir is missing or not a directory"
            )
        text = resolve_inductive_fidelity(key, indir)
        if text is None:
            # Directory exists; section JSON absent or empty decisions → empty i_star
            return "", None
        return text, None

    path = partition_path(rev)
    if not path.is_file():
        return "", f"partition file not found: {path}"
    try:
        atoms = load_partition(path)
    except ValueError as exc:
        return "", str(exc)
    return filter_i_star(atoms, key), None


def cmd_resolve_i_star(args: argparse.Namespace) -> int:
    prose, error = resolve_i_star_text(
        revision_dir=args.revision_dir,
        section=args.section,
        profile_id=args.profile,
        project_root=args.project_root,
        inductive_dir=args.inductive_dir,
    )
    if error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    if not prose.strip():
        print(
            f"resolve-i-star: empty i_star for section={args.section.strip().upper()}",
            file=sys.stderr,
        )
    print(prose, end="" if prose.endswith("\n") or not prose else "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_p = sub.add_parser(
        "resolve-i-star",
        help="Print i_star prose for one section (key off drafting.inductive)",
    )
    resolve_p.add_argument("--revision-dir", type=Path, required=True)
    resolve_p.add_argument("--section", type=str, required=True)
    resolve_p.add_argument("--profile", type=str, required=True)
    resolve_p.add_argument("--project-root", type=Path, default=Path.cwd())
    resolve_p.add_argument(
        "--inductive-dir",
        type=Path,
        default=None,
        help="Required when drafting.inductive is true",
    )
    resolve_p.set_defaults(func=cmd_resolve_i_star)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Host project root is the process cwd.

``--project-root`` is optional. When passed it must resolve to cwd.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional


class ProjectRootMismatch(ValueError):
    """Raised when --project-root resolves to a path other than cwd."""


def resolve_host_project_root(raw: Optional[Path | str] = None) -> Path:
    """Return cwd. Reject a passed path that is not cwd."""
    cwd = Path.cwd().resolve()
    if raw is None:
        return cwd
    if isinstance(raw, str) and not raw.strip():
        return cwd
    passed = Path(raw).expanduser().resolve()
    if passed != cwd:
        raise ProjectRootMismatch(
            f"--project-root must equal process cwd: got {passed.as_posix()}, "
            f"cwd {cwd.as_posix()}"
        )
    return cwd


def add_project_root_option(parser: argparse.ArgumentParser) -> None:
    """Register optional --project-root (cwd when omitted)."""
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Must equal process cwd when passed. Omit to use cwd.",
    )


def apply_project_root_arg(args: argparse.Namespace) -> Path:
    """Resolve args.project_root onto cwd or exit 1 on mismatch."""
    try:
        root = resolve_host_project_root(getattr(args, "project_root", None))
    except ProjectRootMismatch as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    args.project_root = root
    return root

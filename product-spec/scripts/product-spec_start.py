#!/usr/bin/env python3
"""product-spec entrypoint for compose-kernel start (injects StartAdapter)."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]
_STAGE_START = Path(__file__).resolve().parent / "start"
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
_KERNEL_CORE = _KERNEL_SCRIPTS / "core"
_START = _KERNEL_SCRIPTS / "start"
for path in (_KERNEL_SCRIPTS, _KERNEL_CORE, _START, _STAGE_START):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from start import parse_args, run_start  # noqa: E402
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402


def main() -> int:
    return run_start(parse_args(), ProductSpecStartAdapter())


if __name__ == "__main__":
    raise SystemExit(main())

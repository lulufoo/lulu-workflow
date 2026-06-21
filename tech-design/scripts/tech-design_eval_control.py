#!/usr/bin/env python3
"""tech-design entrypoint for eval control (injects WorkflowAdapter)."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
_EVAL_ADAPTER_DIR = Path(__file__).resolve().parent / "eval"
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
for path in (_EVAL_SCRIPTS, _EVAL_ADAPTER_DIR, _KERNEL_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from eval_control import parse_args, run_eval  # noqa: E402
from tech_design_eval_adapter import TechDesignEvalAdapter  # noqa: E402


def main() -> int:
    return run_eval(parse_args(), TechDesignEvalAdapter())


if __name__ == "__main__":
    raise SystemExit(main())

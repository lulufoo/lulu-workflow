#!/usr/bin/env python3
"""Workflow-neutral Eval entrypoint via the adapter registry.

The selected adapter owns workflow-specific handoff and lifecycle mechanics;
this entry only loads it and invokes the shared Eval control plane.

Invoke via the ``$EVAL_CONTROL`` macro (see ``eval/SKILL.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_EVAL_SCRIPTS = Path(__file__).resolve().parent
if str(_EVAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_EVAL_SCRIPTS))

from eval_control import parse_args, run_eval  # noqa: E402
from eval_adapter_registry import load_eval_adapter  # noqa: E402


def main() -> int:
    args = parse_args()
    workflow_id = args.workflow.strip()
    cycle_id = args.cycle_id.strip()
    project_root = args.project_root.resolve()

    # init-round / begin-eval-round may run while preparing evaluating
    require_evaluating = args.command not in {
        "init-round",
        "begin-eval-round",
    }
    try:
        adapter = load_eval_adapter(workflow_id)
        handoff = adapter.request_eval_handoff(
            cycle_id=cycle_id,
            project_root=project_root,
            require_evaluating=require_evaluating,
        )
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return run_eval(args, adapter, handoff=handoff)


if __name__ == "__main__":
    raise SystemExit(main())

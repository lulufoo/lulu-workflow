#!/usr/bin/env python3
"""Profile-driven eval entrypoint via Compose EvalHandoff.

Compose owns profile parsing and L directory resolution. This entry:
1. Requests EvalHandoff from Compose (AdapterRef + EvalContext)
2. Loads the stage WorkflowAdapter from AdapterRef
3. Runs eval_control with the handoff injected

Invoke via the ``$EVAL_CONTROL`` macro (see ``eval/SKILL.md``).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_EVAL_SCRIPTS = Path(__file__).resolve().parent
if str(_EVAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_EVAL_SCRIPTS))

_WORKFLOW_ROOT = _EVAL_SCRIPTS.parent.parent
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from eval_handoff_control import request_handoff  # noqa: E402
from eval_control import parse_args, run_eval  # noqa: E402
from workflow_adapter import WorkflowAdapter  # noqa: E402


def load_eval_adapter_from_ref(adapter_ref: dict[str, str]) -> WorkflowAdapter:
    """Instantiate WorkflowAdapter from Compose AdapterRef (absolute module path)."""
    adapter_module = str(adapter_ref.get("adapter_module", "")).strip()
    adapter_class = str(adapter_ref.get("adapter_class", "")).strip()
    if not adapter_module:
        raise ValueError("AdapterRef.adapter_module is required")
    if not adapter_class:
        raise ValueError("AdapterRef.adapter_class is required")

    adapter_path = Path(adapter_module)
    if not adapter_path.is_file():
        raise ValueError(f"adapter_module not found: {adapter_path.as_posix()}")

    plugin_id = str(adapter_ref.get("workflow_id", "eval")).strip() or "eval"
    module_name = f"_compose_eval_adapter_{plugin_id}"
    spec = importlib.util.spec_from_file_location(module_name, adapter_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load adapter_module: {adapter_path.as_posix()}")

    adapter_dir = str(adapter_path.parent)
    if adapter_dir not in sys.path:
        sys.path.insert(0, adapter_dir)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter_type = getattr(module, adapter_class, None)
    if adapter_type is None:
        raise ValueError(
            f"adapter class {adapter_class!r} not found in {adapter_path.as_posix()}",
        )
    return adapter_type()


def _request_compose_handoff(
    *,
    workflow_id: str,
    cycle_id: str,
    project_root: Path,
    require_evaluating: bool,
) -> dict[str, Any]:
    result = request_handoff(
        cycle_id,
        project_root,
        profile_id=workflow_id,
        require_evaluating=require_evaluating,
    )
    if not result.get("ok"):
        raise ValueError(result.get("error") or "Compose request-handoff failed")
    handoff = result.get("handoff")
    if not isinstance(handoff, dict):
        raise ValueError("Compose handoff missing")
    return handoff


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
        handoff = _request_compose_handoff(
            workflow_id=workflow_id,
            cycle_id=cycle_id,
            project_root=project_root,
            require_evaluating=require_evaluating,
        )
        adapter = load_eval_adapter_from_ref(handoff["adapter"])
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return run_eval(args, adapter, handoff=handoff)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Profile-driven eval entrypoint.

Dynamically loads the WorkflowAdapter declared by a stage's
``compose-profile.json`` (``eval.adapter_module`` / ``eval.adapter_class``),
mirroring how ``compose/scripts/core/start.py`` loads a StartAdapter.
Replaces the deleted per-stage ``{stage}_eval_control.py`` boilerplate
entrypoints; invoke via the ``$EVAL_CONTROL`` macro (see ``eval/SKILL.md``).
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
from workflow_paths import compose_profile_path, load_profile_json  # noqa: E402

from eval_control import parse_args, run_eval  # noqa: E402
from workflow_adapter import WorkflowAdapter  # noqa: E402


def load_eval_adapter(profile: dict[str, Any], profile_json_path: Path) -> WorkflowAdapter:
    """Instantiate the WorkflowAdapter declared by profile.eval (mirrors start.py's load_start_adapter)."""
    eval_config = profile.get("eval") or {}
    adapter_module = str(eval_config.get("adapter_module", "")).strip()
    adapter_class = str(eval_config.get("adapter_class", "")).strip()
    if not adapter_module:
        raise ValueError("profile.eval.adapter_module is required")
    if not adapter_class:
        raise ValueError("profile.eval.adapter_class is required")

    workflow_root = profile_json_path.resolve().parent.parent
    adapter_path = Path(adapter_module)
    if not adapter_path.is_absolute():
        adapter_path = (workflow_root / adapter_path).resolve()
    if not adapter_path.is_file():
        raise ValueError(f"eval.adapter_module not found: {adapter_path.as_posix()}")

    module_name = f"_compose_eval_adapter_{profile.get('profile_id', profile_json_path.parent.name)}"
    spec = importlib.util.spec_from_file_location(module_name, adapter_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load eval.adapter_module: {adapter_path.as_posix()}")

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


def main() -> int:
    args = parse_args()
    profile_id = args.workflow.strip()
    profile_json_path = compose_profile_path(profile_id)
    try:
        profile = load_profile_json(profile_json_path)
        if str(profile.get("profile_id", "")).strip() != profile_id:
            raise ValueError(
                f"profile_id mismatch: --workflow {profile_id!r} vs "
                f"JSON {profile.get('profile_id')!r}",
            )
        adapter = load_eval_adapter(profile, profile_json_path)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return run_eval(args, adapter)


if __name__ == "__main__":
    raise SystemExit(main())

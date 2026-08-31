#!/usr/bin/env python3
"""Workflow-neutral Eval entrypoint via caller-supplied adapter config JSON.

Callers (Compose / Decision) pass ``--adapter-config-file`` or ``--adapter-config``.
Eval does not discover stages or read a central registry.

Invoke via the ``$EVAL_CONTROL`` macro defined in ``eval/SKILL.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EVAL_SCRIPTS = Path(__file__).resolve().parent
if str(_EVAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_EVAL_SCRIPTS))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()

from eval_adapter_config import (  # noqa: E402
    load_adapter_config_file,
    load_adapter_config_json,
    load_eval_adapter_from_config,
    validate_adapter_methods,
    validate_adapter_protocol,
)

_DEFER_HANDOFF_COMMANDS = frozenset({"init-round", "begin-eval-round"})
from eval_control import build_parser, run_eval  # noqa: E402


def parse_entry_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse Eval entry args (adapter config + shared control args)."""
    parser = build_parser()
    parser.add_argument(
        "--adapter-config-file",
        type=Path,
        default=None,
        help="Path to JSON adapter config (Compose/Decision passthrough)",
    )
    parser.add_argument(
        "--adapter-config",
        default=None,
        help="Inline JSON adapter config object",
    )
    return parser.parse_args(argv)


def _load_config(args: argparse.Namespace):
    file_path = args.adapter_config_file
    inline = args.adapter_config
    if file_path and inline:
        raise ValueError(
            "pass only one of --adapter-config-file or --adapter-config",
        )
    if file_path is not None:
        return load_adapter_config_file(Path(file_path))
    if inline is not None and str(inline).strip():
        return load_adapter_config_json(str(inline))
    raise ValueError(
        "adapter config required: pass --adapter-config-file or --adapter-config",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_entry_args(argv)
    cycle_id = args.cycle_id.strip()
    project_root = args.project_root.resolve()

    try:
        config = _load_config(args)
        args.workflow = config.workflow_id
        adapter = load_eval_adapter_from_config(config)
        validate_adapter_methods(adapter, eval_capability=config.eval_capability)
        handoff = None
        if args.command not in _DEFER_HANDOFF_COMMANDS:
            handoff = adapter.request_eval_handoff(
                cycle_id=cycle_id,
                project_root=project_root,
                require_evaluating=True,
            )
            validate_adapter_protocol(
                adapter,
                eval_capability=config.eval_capability,
                handoff=handoff,
            )
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return run_eval(args, adapter, handoff=handoff)


if __name__ == "__main__":
    raise SystemExit(main())

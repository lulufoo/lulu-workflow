#!/usr/bin/env python3
"""Compose entry: stage compose-profile.eval → decorator adapter envelope.

Stage profile remains the Contributor SSOT. This control derives the runtime
envelope Eval Loader consumes and invokes ``eval/scripts/eval_entry.py``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_eval_envelope import build_compose_eval_envelope  # noqa: E402
from workflow_paths import (  # noqa: E402
    WORKFLOW_ROOT,
    load_profile,
    resolve_profile_id,
)

_EVAL_ENTRY = WORKFLOW_ROOT / "eval" / "scripts" / "eval_entry.py"


def _emit_error(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def extract_eval_adapter_config(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the derived decorator envelope for Eval."""
    return build_compose_eval_envelope(profile)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compose Eval control — passthrough stage eval config to Eval",
    )
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "eval_args",
        nargs=argparse.REMAINDER,
        help="Eval subcommand and args (e.g. begin-eval-round)",
    )
    args = parser.parse_args(argv)

    remainder = list(args.eval_args)
    if remainder and remainder[0] == "--":
        remainder = remainder[1:]
    if not remainder:
        return _emit_error("missing Eval subcommand after --cycle-id")

    project_root = args.project_root.resolve()
    try:
        profile_id = resolve_profile_id(
            project_root=project_root,
            cycle_id=args.cycle_id.strip(),
        )
        profile = load_profile(
            profile_id,
            project_root=project_root,
            cycle_id=args.cycle_id.strip(),
        )
        config = extract_eval_adapter_config(profile)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _emit_error(str(exc))

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="eval-adapter-config-",
        delete=False,
        encoding="utf-8",
    ) as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        config_path = Path(handle.name)

    cmd = [
        sys.executable,
        str(_EVAL_ENTRY),
        "--adapter-config-file",
        str(config_path),
        "--cycle-id",
        args.cycle_id.strip(),
        "--project-root",
        str(project_root),
        *remainder,
    ]
    try:
        completed = subprocess.run(cmd, check=False)
        return int(completed.returncode)
    finally:
        try:
            config_path.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compose passthrough entry: stage compose-profile.eval → Eval adapter config.

Does not invent a second config source. Loads the active stage profile's ``eval``
object and invokes ``eval/scripts/eval_entry.py`` with ``--adapter-config-file``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

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
    """Return the profile ``eval`` object for Eval (passthrough)."""
    eval_block = profile.get("eval")
    if not isinstance(eval_block, dict):
        raise ValueError("compose-profile.json missing object field 'eval'")
    if "adapter_module" not in eval_block or "adapter_class" not in eval_block:
        raise ValueError(
            "compose-profile.json eval must include adapter_module and adapter_class",
        )
    # Passthrough: keep workflow_id / enabled and any future keys.
    return dict(eval_block)


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

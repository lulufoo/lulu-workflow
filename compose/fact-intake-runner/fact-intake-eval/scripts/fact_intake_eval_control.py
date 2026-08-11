#!/usr/bin/env python3
"""Atomize-eval entry: fixed adapter-config → eval_entry (independent of delivery Eval).

Sets COMPOSE_ATOMIZE_PROFILE_ID so the adapter can resolve the compose revision.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_ATOMIZE_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_EVAL_ENTRY = _WORKFLOW_ROOT / "eval" / "scripts" / "eval_entry.py"
_PROFILE_PATH = _ATOMIZE_ROOT / "eval-profile.json"
_PROFILE_ENV = "COMPOSE_ATOMIZE_PROFILE_ID"


def _emit_error(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def load_atomize_adapter_config() -> dict:
    data = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("atomize eval-profile.json must be an object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Atomize Eval control — fixed compose atomize-eval adapter config",
    )
    parser.add_argument(
        "--profile-id",
        required=True,
        help="Compose stage profile id (e.g. lulu-plan) for revision resolution",
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
        return _emit_error("missing Eval subcommand after --profile-id / --cycle-id")

    try:
        config = load_atomize_adapter_config()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))

    project_root = args.project_root.resolve()
    profile_id = args.profile_id.strip()
    env = os.environ.copy()
    env[_PROFILE_ENV] = profile_id

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="atomize-eval-adapter-config-",
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
        completed = subprocess.run(cmd, check=False, env=env)
        return int(completed.returncode)
    finally:
        try:
            config_path.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

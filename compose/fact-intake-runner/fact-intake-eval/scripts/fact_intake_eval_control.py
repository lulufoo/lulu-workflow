#!/usr/bin/env python3
"""Fact-intake-eval entry: fixed adapter-config → eval_entry (independent of delivery Eval).

Sets COMPOSE_FACT_INTAKE_PROFILE_ID so the adapter can resolve the compose revision.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_INTAKE_EVAL_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = Path(__file__).resolve().parents[4]
_COMPOSE_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
_EVAL_ENTRY = _WORKFLOW_ROOT / "eval" / "scripts" / "eval_entry.py"
_PROFILE_PATH = _INTAKE_EVAL_ROOT / "eval-profile.json"
_PROFILE_ENV = "COMPOSE_FACT_INTAKE_PROFILE_ID"

if str(_COMPOSE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_COMPOSE_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import resolve_profile_id  # noqa: E402


def _emit_error(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def load_fact_intake_adapter_config() -> dict:
    data = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fact-intake eval-profile.json must be an object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fact Intake Eval control — fixed compose fact-intake-eval adapter config",
    )
    parser.add_argument(
        "--profile-id",
        default="",
        help="Compose stage profile id (default: cycle context after start)",
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
        config = load_fact_intake_adapter_config()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))

    project_root = args.project_root.resolve()
    try:
        profile_id = resolve_profile_id(
            project_root=project_root,
            cycle_id=args.cycle_id.strip(),
            explicit=args.profile_id,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        return _emit_error(str(exc))
    env = os.environ.copy()
    env[_PROFILE_ENV] = profile_id

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="fact-intake-eval-adapter-config-",
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

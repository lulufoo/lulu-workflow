#!/usr/bin/env python3
"""Fact-intake-eval: emit adapter-config for $EVAL_CONTROL.

Writes eval-profile.json plus adapter_options.profile_id. Does not invoke
eval_entry.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_INTAKE_EVAL_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = Path(__file__).resolve().parents[4]
_COMPOSE_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
_PROFILE_PATH = _INTAKE_EVAL_ROOT / "eval-profile.json"

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


def default_adapter_config_path(project_root: Path, cycle_id: str) -> Path:
    return project_root / ".cache" / "fact-intake-eval-adapter" / f"{cycle_id}.json"


def write_adapter_config(
    cycle_id: str,
    project_root: Path,
    *,
    output: Path | None = None,
) -> Path:
    """Copy the packaged profile and bind this cycle's profile_id."""
    config = load_fact_intake_adapter_config()
    profile_id = resolve_profile_id(
        project_root=project_root,
        cycle_id=cycle_id,
    )
    options = config.get("adapter_options")
    if not isinstance(options, dict):
        options = {}
    options["profile_id"] = profile_id
    config["adapter_options"] = options
    path = (output or default_adapter_config_path(project_root, cycle_id)).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fact Intake Eval — emit adapter-config file for $EVAL_CONTROL",
    )
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Adapter-config JSON path (default: .cache/fact-intake-eval-adapter/<cycle>.json)",
    )
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    try:
        path = write_adapter_config(
            args.cycle_id.strip(),
            project_root,
            output=args.output,
        )
    except (OSError, ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
        return _emit_error(str(exc))

    print(
        json.dumps(
            {"ok": True, "adapter_config_file": path.as_posix()},
            ensure_ascii=False,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

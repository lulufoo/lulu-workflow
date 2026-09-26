#!/usr/bin/env python3
"""Compose: derive decorator envelope and emit adapter-config for $EVAL_CONTROL.

Stage profile remains the Contributor SSOT. This control writes the runtime
envelope Eval Loader consumes. It does not start the Eval process.
"""

from __future__ import annotations

import argparse
import json
import sys
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
    load_profile,
    resolve_profile_id,
)


def _emit_error(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def extract_eval_adapter_config(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the derived decorator envelope for Eval."""
    return build_compose_eval_envelope(profile)


def default_adapter_config_path(project_root: Path, cycle_id: str) -> Path:
    return project_root / ".cache" / "compose-eval-adapter" / f"{cycle_id}.json"


def write_adapter_config(
    cycle_id: str,
    project_root: Path,
    *,
    output: Path | None = None,
) -> Path:
    """Derive the envelope and write it. Return the absolute path."""
    profile_id = resolve_profile_id(
        project_root=project_root,
        cycle_id=cycle_id,
    )
    profile = load_profile(
        profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
    )
    config = extract_eval_adapter_config(profile)
    path = (output or default_adapter_config_path(project_root, cycle_id)).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compose Eval adapter — emit adapter-config file for $EVAL_CONTROL",
    )
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Adapter-config JSON path (default: .cache/compose-eval-adapter/<cycle>.json)",
    )
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    try:
        path = write_adapter_config(
            args.cycle_id.strip(),
            project_root,
            output=args.output,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
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

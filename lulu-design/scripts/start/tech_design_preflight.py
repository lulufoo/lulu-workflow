#!/usr/bin/env python3
"""lulu-design preflight: runtime profile + normalized scope-package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
_START = _KERNEL_SCRIPTS / "scope"
for p in (_KERNEL_SCRIPTS, _START, Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from holder_preflight_support import (  # noqa: E402
    emit_ok,
    preflight_dir,
    print_preflight,
    run_scope_preflight,
    write_profile_bytes,
)
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402

_TEMPLATE = Path(__file__).resolve().parents[2] / "compose-profile.json"
_CACHE_SUBDIR = "lulu-design"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="lulu-design compose preflight")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--cycle-id", required=True)
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve()
    cycle_id = args.cycle_id.strip()
    try:
        out = preflight_dir(root, cycle_id, _CACHE_SUBDIR)
        profile = write_profile_bytes(_TEMPLATE, out)
        scope = run_scope_preflight(
            adapter=TechDesignStartAdapter(),
            cycle_id=cycle_id,
            project_root=root,
            output_dir=out,
        )
        return print_preflight(emit_ok(profile_path=profile, scope_package=scope))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "command": "preflight", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

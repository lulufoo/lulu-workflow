
_here = Path(__file__).resolve().parent
for _parent in [_here, *_here.parents]:
    _scripts = _parent if (_parent / "project_root.py").is_file() else _parent / "scripts"
    if (_scripts / "project_root.py").is_file():
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        break
from project_root import apply_project_root_arg  # noqa: E402

#!/usr/bin/env python3
"""lulu-tasks project init — workflow-config is applied via lulu-workflow configure only."""

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="lulu-tasks sub-init (no workflow-config writes).",
    )
    parser.add_argument("--project-root", help="Project root directory.")
    args = parser.parse_args()
    apply_project_root_arg(args)
    return args


def main() -> int:
    parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

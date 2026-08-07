#!/usr/bin/env python3
"""DELETED — ``_chapters.json`` and archive-3.0 chapter-plan CLI removed.

Use ``narrative_arc_control.py`` (``_narrative-arc.json``) instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "错误：chapters_control / _chapters.json retired. "
        "Use narrative-arc-runner/scripts/narrative_arc_control.py "
        "(validate|write|show|list-chapters).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

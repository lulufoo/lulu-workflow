#!/usr/bin/env python3
"""RETIRED — ``_chapters.json`` removed (archive-3.0).

Use ``chapter_plan_control.py`` (themes / framework / placement) instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "错误：chapters_control / _chapters.json retired. "
        "Use chapter_plan_control.py "
        "(write-themes|write-framework|write-placement|list-chapters|validate).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

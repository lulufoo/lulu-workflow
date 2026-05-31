#!/usr/bin/env python3
"""Stage guard: code stage has no write restrictions."""

import json
import sys


def main() -> int:
    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

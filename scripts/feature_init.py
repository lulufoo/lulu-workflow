#!/usr/bin/env python3
"""feature_init.py — Initialize a new lulu-dev-workflow feature.

Usage:
    python3 feature_init.py --project-root <path> --name "<feature-name>"

Output (stdout last line): feature_id
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# ---------------------------------------------------------------------------
# Platform detection (same pattern as workflow_common.py / archive_common.py)
# ---------------------------------------------------------------------------

_PLATFORM = (
    os.environ.get("LULU_PLATFORM")
    or ("copilot" if os.environ.get("COPILOT_AGENT") else "cursor")
)


def _cache_dir(project_root: Path) -> Path:
    return project_root / ".cache" / _PLATFORM / "lulu-dev-workflow"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def generate_feature_id() -> str:
    """Return a feature ID: YYYYMMDDHHMMSS-{8hexchars}."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    hex_part = uuid4().hex[:8]
    return f"{ts}-{hex_part}"


def ensure_feature_dir(cache_dir: Path, feature_id: str) -> Path:
    """Create cache_dir/{feature_id}/ and return its Path."""
    target = cache_dir / feature_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def update_features_json(cache_dir: Path, feature_id: str, name: str, mode: str = "assisted") -> None:
    """Append {feature_id: {name, execution_mode}} to features.json (create if absent)."""
    fj = cache_dir / "features.json"
    if fj.exists():
        data: dict = json.loads(fj.read_text(encoding="utf-8"))
    else:
        data = {}
    data[feature_id] = {"name": name, "execution_mode": mode}
    fj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main(project_root: Path, name: str, mode: str = "assisted") -> str:
    """Orchestrate feature initialization. Returns feature_id."""
    if not project_root.is_dir():
        print(f"Error: --project-root does not exist: {project_root}", file=sys.stderr)
        sys.exit(1)

    cache_dir = _cache_dir(project_root)
    cache_dir.mkdir(parents=True, exist_ok=True)

    feature_id = generate_feature_id()
    ensure_feature_dir(cache_dir, feature_id)
    update_features_json(cache_dir, feature_id, name, mode)

    print(feature_id)
    return feature_id


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize a new lulu-dev-workflow feature."
    )
    parser.add_argument("--project-root", required=True, help="Workspace root path")
    parser.add_argument("--name", required=True, help="Human-readable feature name")
    parser.add_argument(
        "--mode",
        choices=["assisted", "self-service"],
        default="assisted",
        help="Execution mode: assisted (default) or self-service",
    )
    args, _ = parser.parse_known_args()

    main(Path(args.project_root), args.name, args.mode)

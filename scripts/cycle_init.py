#!/usr/bin/env python3
"""cycle_init.py — Initialize a new lulu-dev-workflow feature.

Usage:
    python3 cycle_init.py --project-root <path> --name "<feature-name>"

Output (stdout last line): cycle_id
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

def generate_cycle_id() -> str:
    """Return a cycle ID: YYYYMMDDHHMMSS-{8hexchars}."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    hex_part = uuid4().hex[:8]
    return f"{ts}-{hex_part}"


def generate_topic_id() -> str:
    """Return a topic ID: topic-YYYYMMDDHHMMSS-{8hexchars}."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    hex_part = uuid4().hex[:8]
    return f"topic-{ts}-{hex_part}"


def ensure_feature_dir(cache_dir: Path, cycle_id: str) -> Path:
    """Create cache_dir/{cycle_id}/ and return its Path."""
    target = cache_dir / cycle_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def ensure_container_dir(cache_dir: Path, cycle_id: str) -> Path:
    """Create cache_dir/{cycle_id}/ and return its Path."""
    target = cache_dir / cycle_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def update_features_json(
    cache_dir: Path,
    cycle_id: str,
    name: str,
    mode: str = "copilot",
    topic_id: str = None,
) -> None:
    """Append {cycle_id: {name, execution_mode[, topic_id]}} to features.json."""
    fj = cache_dir / "features.json"
    if fj.exists():
        data: dict = json.loads(fj.read_text(encoding="utf-8"))
    else:
        data = {}
    entry = {"name": name, "execution_mode": mode}
    if topic_id is not None:
        entry["topic_id"] = topic_id
    data[cycle_id] = entry
    fj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_topics_json(
    cache_dir: Path,
    topic_id: str,
    name: str,
    mode: str = "copilot",
) -> None:
    """Append {topic_id: {name, execution_mode}} to topics.json (create if absent)."""
    tj = cache_dir / "topics.json"
    if tj.exists():
        data: dict = json.loads(tj.read_text(encoding="utf-8"))
    else:
        data = {}
    data[topic_id] = {"name": name, "execution_mode": mode}
    tj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_topic_exists(cache_dir: Path, topic_id: str) -> bool:
    """Return True if topic_id exists in topics.json; False if absent or not found."""
    tj = cache_dir / "topics.json"
    if not tj.exists():
        return False
    data: dict = json.loads(tj.read_text(encoding="utf-8"))
    return topic_id in data


def main(project_root: Path, name: str, mode: str = "copilot", cycle_type: str = "feature", topic_id: str = None) -> str:
    """Orchestrate initialization. Returns cycle_id."""
    if not project_root.is_dir():
        print(f"Error: --project-root does not exist: {project_root}", file=sys.stderr)
        sys.exit(1)

    cache_dir = _cache_dir(project_root)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if cycle_type == "topic":
        cycle_id = generate_topic_id()
        ensure_container_dir(cache_dir, cycle_id)
        update_topics_json(cache_dir, cycle_id, name, mode)
    else:
        if topic_id is not None and not validate_topic_exists(cache_dir, topic_id):
            print(f"Error: topic_id not found in topics.json: {topic_id}", file=sys.stderr)
            sys.exit(1)
        cycle_id = generate_cycle_id()
        ensure_feature_dir(cache_dir, cycle_id)
        update_features_json(cache_dir, cycle_id, name, mode, topic_id=topic_id)

    print(cycle_id)
    return cycle_id


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize a new lulu-dev-workflow container (feature or topic)."
    )
    parser.add_argument("--project-root", required=True, help="Workspace root path")
    parser.add_argument("--name", required=True, help="Human-readable name")
    parser.add_argument(
        "--mode",
        choices=["copilot", "autonomous"],
        default="copilot",
        help="Execution mode: copilot (default) or autonomous",
    )
    parser.add_argument(
        "--type",
        choices=["topic", "feature"],
        required=True,
        dest="cycle_type",
        help="Container type: topic or feature",
    )
    parser.add_argument(
        "--topic-id",
        default=None,
        help="Associate this feature with an existing topic (only valid with --type feature)",
    )
    args = parser.parse_known_args()[0]

    main(Path(args.project_root), args.name, args.mode, args.cycle_type, args.topic_id)

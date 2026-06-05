#!/usr/bin/env python3
"""prune_features.py — Prune old feature dirs, keeping the N most recent.

Usage:
    python3 prune_features.py --project-root <path> [--keep N]

Sorts cycle_ids lexicographically (YYYYMMDDHHMMSS prefix → chronological),
keeps the N most recent, deletes older feature directories from $CACHE_DIR,
and rewrites features.json to match.
"""

import argparse
import json
import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Platform detection (same pattern as cycle_init.py / archive_common.py)
# ---------------------------------------------------------------------------

_PLATFORM = (
    os.environ.get("LULU_PLATFORM")
    or ("copilot" if os.environ.get("COPILOT_AGENT") else "cursor")
)


def _cache_dir(project_root: Path) -> Path:
    return project_root / ".cache" / _PLATFORM / "lulu-dev-workflow"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def prune(project_root: Path, keep: int) -> None:
    cache = _cache_dir(project_root)
    features_json = cache / "features.json"

    if not features_json.exists():
        print("features.json not found — nothing to prune.")
        return

    with open(features_json, encoding="utf-8") as f:
        features: dict = json.load(f)

    sorted_ids = sorted(features.keys())  # lexicographic = chronological

    if len(sorted_ids) <= keep:
        print(
            f"Nothing to prune — total features: {len(sorted_ids)}, "
            f"keep: {keep}."
        )
        return

    keep_ids = set(sorted_ids[-keep:])
    delete_ids = [fid for fid in sorted_ids if fid not in keep_ids]

    deleted, skipped = [], []
    for fid in delete_ids:
        feature_dir = cache / fid
        if feature_dir.exists():
            shutil.rmtree(feature_dir)
            deleted.append(fid)
            print(f"Deleted: {feature_dir.relative_to(project_root)}")
        else:
            skipped.append(fid)
            print(f"Directory not found (removed from index only): {fid}")

    pruned_features = {fid: features[fid] for fid in sorted_ids if fid in keep_ids}
    with open(features_json, "w", encoding="utf-8") as f:
        json.dump(pruned_features, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(
        f"\nDone — deleted {len(deleted)} dir(s), "
        f"cleaned {len(skipped)} stale index entr(ies), "
        f"kept {len(keep_ids)} most recent feature(s)."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prune old lulu-dev-workflow feature directories."
    )
    parser.add_argument(
        "--project-root",
        required=True,
        metavar="PATH",
        help="Absolute path to the project root.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=5,
        metavar="N",
        help="Number of most-recent features to keep (default: 5).",
    )
    args, _ = parser.parse_known_args()

    if args.keep < 1:
        parser.error("--keep must be at least 1")

    prune(Path(args.project_root).resolve(), args.keep)


if __name__ == "__main__":
    main()

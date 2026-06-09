#!/usr/bin/env python3
"""Fetch workflow template markdown from workflow-config.json with local cache."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from subagent_config import detect_platform, resolve_workflow_config_path

CACHE_ROOT_NAME = "lulu-dev-workflow"
CACHE_TEMPLATE_SUBDIR = ".template"

_BLOB_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/(?P<rest>.+)$"
)

# Parse refs from right to left by locating known template roots.
# This avoids incorrectly splitting multi-segment refs as path.
_KNOWN_TEMPLATE_ROOTS: tuple[tuple[str, ...], ...] = (
    ("lulu-dev-workflow", "template"),
)

GhFetcher = Callable[[str, str, str, str], str]


class FetchTemplateError(Exception):
    """Raised when template fetch fails."""


def cache_path(
    project_root: Path,
    platform: str,
    section: str,
    key: str,
) -> Path:
    return (
        project_root
        / ".cache"
        / platform
        / CACHE_ROOT_NAME
        / CACHE_TEMPLATE_SUBDIR
        / section
        / f"{key}.md"
    )


def parse_blob_url(url: str) -> dict[str, str]:
    match = _BLOB_RE.match(url.strip())
    if not match:
        raise FetchTemplateError(f"Not a GitHub blob URL: {url}")
    base = match.groupdict()
    rest = base["rest"]
    parts = [p for p in rest.split("/") if p]
    if len(parts) < 2:
        raise FetchTemplateError(f"Ambiguous GitHub blob URL (missing path): {url}")

    candidates: list[tuple[str, str]] = []
    for root in _KNOWN_TEMPLATE_ROOTS:
        root_len = len(root)
        for idx in range(1, len(parts) - root_len + 1):
            if tuple(parts[idx : idx + root_len]) != root:
                continue
            ref_parts = parts[:idx]
            path_parts = parts[idx:]
            if not ref_parts or not path_parts:
                continue
            candidates.append(("/".join(ref_parts), "/".join(path_parts)))

    if len(candidates) == 1:
        ref, path = candidates[0]
        return {
            "owner": base["owner"],
            "repo": base["repo"],
            "ref": ref,
            "path": path,
        }
    if len(candidates) > 1:
        raise FetchTemplateError(f"Ambiguous GitHub blob URL (multiple roots): {url}")

    # Without a known root, only a single-segment ref can be parsed unambiguously.
    if len(parts) == 2:
        return {
            "owner": base["owner"],
            "repo": base["repo"],
            "ref": parts[0],
            "path": parts[1],
        }
    raise FetchTemplateError(f"Ambiguous GitHub blob URL (cannot resolve ref/path): {url}")


def gh_api_fetch(owner: str, repo: str, ref: str, path: str) -> str:
    api_path = f"repos/{owner}/{repo}/contents/{path}?ref={ref}"
    try:
        result = subprocess.run(
            ["gh", "api", api_path, "--jq", ".content"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FetchTemplateError("gh CLI not found; install and authenticate gh") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "gh api failed"
        raise FetchTemplateError(detail)

    encoded = result.stdout.strip()
    if not encoded:
        raise FetchTemplateError("gh api returned empty content")

    try:
        return base64.b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise FetchTemplateError("Failed to decode gh api content") from exc


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def read_config_url(config_path: Path, section: str, key: str) -> str:
    if not config_path.exists():
        raise FetchTemplateError(f"workflow-config not found: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise FetchTemplateError(f"Invalid workflow-config: {config_path}") from exc

    section_cfg = config.get(section)
    if not isinstance(section_cfg, dict):
        raise FetchTemplateError(
            f"Missing section [{section!r}] in {config_path.as_posix()}"
        )

    if key not in section_cfg:
        raise FetchTemplateError(
            f"Missing key [{section}][{key!r}] in {config_path.as_posix()}"
        )

    url = str(section_cfg.get(key, "")).strip()
    if not url:
        raise FetchTemplateError(
            f"Empty URL for [{section}][{key!r}] in {config_path.as_posix()}"
        )
    return url


def fetch_template(
    section: str,
    key: str,
    project_root: Path,
    platform: Optional[str] = None,
    force: bool = False,
    gh_fetcher: GhFetcher = gh_api_fetch,
) -> str:
    plat = detect_platform(platform)
    cache_file = cache_path(project_root, plat, section, key)

    if not force and cache_file.exists():
        cached = cache_file.read_text(encoding="utf-8")
        if cached.strip():
            return cached

    config_path = resolve_workflow_config_path(project_root, plat)
    url = read_config_url(config_path, section, key)
    parsed = parse_blob_url(url)
    content = gh_fetcher(
        parsed["owner"],
        parsed["repo"],
        parsed["ref"],
        parsed["path"],
    )
    atomic_write(cache_file, content)
    return content


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch workflow template markdown via workflow-config.json",
    )
    parser.add_argument("--section", required=True, help="workflow-config section name")
    parser.add_argument("--key", required=True, help="URL field key within section")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--platform",
        choices=["cursor", "copilot"],
        help="Platform cache namespace (default: auto-detect)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass cache and re-fetch from GitHub",
    )
    args = parser.parse_args(argv)

    try:
        content = fetch_template(
            section=args.section,
            key=args.key,
            project_root=Path(args.project_root).resolve(),
            platform=args.platform,
            force=args.force,
        )
    except FetchTemplateError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

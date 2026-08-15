#!/usr/bin/env python3
"""Fetch workflow templates from config keys or direct refs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from platforms.registry import resolve_skill_root
from subagent_config import (
    detect_platform,
    get_stage_config_value,
    load_stage_config,
    stage_config_has_key,
    workflow_config_is_present,
)

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


def normalize_template_ref(template_ref: str) -> str:
    """Normalize a profile template reference without changing its identity."""
    return str(template_ref).strip()


def is_direct_template_ref(template_ref: str) -> bool:
    """Return whether a profile value is a direct local or remote reference."""
    ref = normalize_template_ref(template_ref)
    return ref.startswith(
        ("lulu-dev-workflow/", "file://", "/", "http://", "https://")
    )


def template_ref_file_name(template_ref: str, fallback: str = "template.md") -> str:
    """Return a stable basename for a local path or remote template reference."""
    ref = normalize_template_ref(template_ref)
    if ref.startswith(("http://", "https://")):
        name = Path(urlparse(ref).path).name
    elif ref.startswith("file://"):
        name = Path(ref[7:]).name
    else:
        name = Path(ref).name
    return name or fallback


def _safe_cache_component(value: str) -> str:
    component = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
    return component.strip("-") or "template"


def template_ref_cache_path(
    project_root: Path,
    platform: Optional[str],
    stage: str,
    file_name: str,
    template_ref: str,
) -> Path:
    """Return the cache path for a direct template reference.

    The logical reference is hashed so paths with separators never become
    nested cache directories. The source extension remains at the end.
    """
    ref = normalize_template_ref(template_ref)
    digest = hashlib.sha256(ref.encode("utf-8")).hexdigest()[:16]
    safe_stage = _safe_cache_component(stage)
    safe_name = _safe_cache_component(Path(file_name).name)
    suffix = Path(safe_name).suffix
    stem = safe_name[: -len(suffix)] if suffix else safe_name
    filename = f"{safe_stage}-{stem}-{digest}{suffix}"
    return (
        project_root
        / ".cache"
        / detect_platform(platform)
        / CACHE_ROOT_NAME
        / CACHE_TEMPLATE_SUBDIR
        / filename
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

    # Without a known root, treat the first segment as ref and the rest as path.
    if len(parts) >= 2:
        return {
            "owner": base["owner"],
            "repo": base["repo"],
            "ref": parts[0],
            "path": "/".join(parts[1:]),
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


def read_config_url(
    project_root: Path,
    section: str,
    key: str,
    platform: Optional[str] = None,
) -> str:
    if not workflow_config_is_present(project_root, platform):
        raise FetchTemplateError(
            f"workflow-config not found under {project_root.as_posix()}"
        )

    try:
        section_cfg = load_stage_config(project_root, section, platform)
    except ValueError as exc:
        raise FetchTemplateError(str(exc)) from exc

    if not stage_config_has_key(section_cfg, key):
        raise FetchTemplateError(
            f"Missing key [{section}][{key!r}] in workflow stage config"
        )

    url = get_stage_config_value(project_root, section, key, platform)
    if not url:
        raise FetchTemplateError(
            f"Empty URL for [{section}][{key!r}] in workflow stage config"
        )
    return url


def resolve_local_template_path(
    url: str,
    project_root: Path | None = None,
    *,
    skill_root: Path | None = None,
) -> Path | None:
    """Resolve local template paths (file://, absolute, or skill-runtime ``lulu-dev-workflow/…``).

    The ``lulu-dev-workflow/`` prefix names the skill runtime directory
    (``SKILL_ROOT``). Remaining segments are relative to that root — not
    ``project_root``.
    """
    _ = project_root
    if url.startswith("file://"):
        return Path(url[7:])
    if url.startswith("/") and not url.startswith("//"):
        return Path(url)
    if url.startswith("lulu-dev-workflow/"):
        root = (
            skill_root
            if skill_root is not None
            else resolve_skill_root(script_path=Path(__file__))
        )
        rel = url.split("/", 1)[1]
        return (root.resolve() / rel).resolve()
    return None


def read_local_file(local_path: Path) -> str:
    if not local_path.exists():
        raise FetchTemplateError(f"Local file not found: {local_path}")
    return local_path.read_text(encoding="utf-8")


def fetch_template_ref(
    template_ref: str,
    project_root: Path,
    *,
    stage: str,
    file_name: Optional[str] = None,
    platform: Optional[str] = None,
    force: bool = False,
    gh_fetcher: GhFetcher = gh_api_fetch,
) -> str:
    """Fetch a direct local or GitHub template reference.

    This path intentionally bypasses workflow-config. Legacy config-key
    loading remains available through ``fetch_template``.
    """
    ref = normalize_template_ref(template_ref)
    if not ref:
        raise FetchTemplateError("Empty template reference")

    local_path = resolve_local_template_path(ref, project_root)
    if local_path is not None:
        return read_local_file(local_path)

    cache_file = template_ref_cache_path(
        project_root,
        platform,
        stage,
        file_name or template_ref_file_name(ref),
        ref,
    )
    if not force and cache_file.exists():
        cached = cache_file.read_text(encoding="utf-8")
        if cached.strip():
            return cached

    parsed = parse_blob_url(ref)
    content = gh_fetcher(
        parsed["owner"],
        parsed["repo"],
        parsed["ref"],
        parsed["path"],
    )
    atomic_write(cache_file, content)
    return content


def resolve_template_ref_path(
    template_ref: str,
    project_root: Path,
    *,
    stage: str,
    file_name: Optional[str] = None,
    platform: Optional[str] = None,
    force: bool = False,
    gh_fetcher: GhFetcher = gh_api_fetch,
) -> Path:
    """Return the source path for local refs or cache path for remote refs."""
    ref = normalize_template_ref(template_ref)
    local_path = resolve_local_template_path(ref, project_root)
    if local_path is not None:
        read_local_file(local_path)
        return local_path

    fetch_template_ref(
        ref,
        project_root,
        stage=stage,
        file_name=file_name,
        platform=platform,
        force=force,
        gh_fetcher=gh_fetcher,
    )
    return template_ref_cache_path(
        project_root,
        platform,
        stage,
        file_name or template_ref_file_name(ref),
        ref,
    )


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
    url = read_config_url(project_root, section, key, plat)

    # Skill-runtime / absolute local paths always win over GitHub cache —
    # otherwise switching a config key from a remote blob URL to a skill-local
    # path would keep serving the stale cached remote body until --force.
    local_path = resolve_local_template_path(url, project_root)
    if local_path is not None:
        return read_local_file(local_path)

    if not force and cache_file.exists():
        cached = cache_file.read_text(encoding="utf-8")
        if cached.strip():
            return cached

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

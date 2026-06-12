#!/usr/bin/env python3
"""Load eval SoT / method content from a URL or absolute local path."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from fetch_template import FetchTemplateError, gh_api_fetch, parse_blob_url  # noqa: E402


class UrlFetchError(Exception):
    """Raised when ref cannot be loaded."""


def is_remote_url(ref: str) -> bool:
    """Return True when ref is an http(s) URL."""
    ref = ref.strip()
    return ref.startswith("http://") or ref.startswith("https://")


def read_ref(ref: str, *, project_root: Path | None = None) -> str:
    """Load text from GitHub blob URL or local file path."""
    ref = ref.strip()
    if not ref:
        raise UrlFetchError("empty ref")
    if is_remote_url(ref):
        return _fetch_remote(ref)
    return _read_local(ref, project_root=project_root)


def _read_local(ref: str, *, project_root: Path | None = None) -> str:
    path = Path(ref)
    if not path.is_absolute():
        if project_root is None:
            raise UrlFetchError(f"relative path requires project_root: {ref!r}")
        path = (project_root / path).resolve()
    if not path.is_file():
        raise UrlFetchError(f"file not found: {path}")
    return path.read_text(encoding="utf-8")


def _fetch_remote(url: str) -> str:
    if "github.com" in url and "/blob/" in url:
        try:
            parsed = parse_blob_url(url)
            return gh_api_fetch(
                parsed["owner"],
                parsed["repo"],
                parsed["ref"],
                parsed["path"],
            )
        except FetchTemplateError as exc:
            raise UrlFetchError(str(exc)) from exc
    raise UrlFetchError(f"unsupported remote URL (GitHub blob only): {url}")

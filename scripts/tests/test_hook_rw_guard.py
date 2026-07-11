#!/usr/bin/env python3
"""Tests for scripts/hook/internal_path_guard.py."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_HOOK = _SCRIPTS / "hook"
if str(_HOOK) not in sys.path:
    sys.path.insert(0, str(_HOOK))

from internal_path_guard import (  # noqa: E402
    allowed_dirs_for_tool,
    extract_tool_path,
    normalize_tool_path,
    path_under_any_allowed,
    resolve_allowed_dirs,
)


class TestPathHelpers:
    def test_extract_tool_path_prefers_path(self):
        assert extract_tool_path("Write", {"path": "a.md", "file_path": "b.md"}) == "a.md"

    def test_normalize_relative_path(self, tmp_path):
        target = normalize_tool_path("src/main.py", tmp_path)
        assert target == (tmp_path / "src/main.py").resolve()

    def test_path_under_allowed_root(self, tmp_path):
        roots = resolve_allowed_dirs(tmp_path, ["."])
        inside = tmp_path / "src/x.py"
        inside.parent.mkdir(parents=True, exist_ok=True)
        assert path_under_any_allowed(inside, roots) is True
        outside = Path("/tmp/outside.txt")
        assert path_under_any_allowed(outside, roots) is False

    def test_allowed_dirs_for_tool(self):
        assert allowed_dirs_for_tool("Read", read_dirs=["."], write_dirs=["cache"]) == ["."]
        assert allowed_dirs_for_tool("Write", read_dirs=["."], write_dirs=["cache"]) == ["cache"]

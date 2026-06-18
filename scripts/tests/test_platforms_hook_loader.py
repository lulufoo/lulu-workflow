#!/usr/bin/env python3
"""Tests for platforms.hook.loader."""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from platforms.hook.loader import load_hook_adapter  # noqa: E402
from platforms.registry import PlatformDetectionError  # noqa: E402


class TestHookLoader:
    def test_loads_all_supported_adapters(self):
        for platform in ("cursor", "copilot", "claude"):
            mod = load_hook_adapter(platform)
            assert callable(mod.normalize)
        assert callable(load_hook_adapter("claude").format_response)

    def test_rejects_unknown_platform(self):
        with pytest.raises(PlatformDetectionError):
            load_hook_adapter("unknown")

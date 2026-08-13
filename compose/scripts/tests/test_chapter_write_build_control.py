#!/usr/bin/env python3
"""Tests for chapter-write-runner session context (archive-26.0)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_REPO = Path(__file__).resolve().parents[4]
_CORE = _COMPOSE / "scripts" / "core"
sys.path.insert(0, str(_CORE))
from workflow_paths import seed_revision_profile_pointer  # noqa: E402
_BUILD = (
    _COMPOSE / "chapter-write-runner" / "scripts" / "chapter_write_build_control.py"
)

_ROLE_EXCLUDE = {
    "role_prompt",
    "priority_tendency",
    "completion_bar",
    "version",
    "$schema_id",
    "cycle_type",
}
_DOMAIN_EXCLUDE = {"version", "$schema_id", "cycle_type"}
_EXPRESSION_KEYS = {"register", "carriers", "scannability", "altitude"}


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_BUILD), *argv],
        text=True,
        capture_output=True,
        check=False,
    )


def test_context_filters_role_domain_and_preamble(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    # facts must not appear even if present on disk
    (rev / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "secret fact"}], ensure_ascii=False),
        encoding="utf-8",
    )
    result = _run(
        [
            "context",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--cycle-type",
            "feature",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "context"
    assert payload["phase"] == "session"
    assert "facts" not in payload
    assert "section_registry" not in payload
    role = payload["role"]
    assert set(role) == {"role_id", "expressive_tendency", "vocabulary_domain"}
    assert not (_ROLE_EXCLUDE & set(role))
    domain = payload["domain"]
    assert set(domain) == {
        "domain_id",
        "cognitive_frame",
        "intent_anchor",
        "audience_type",
        "expression_conventions",
    }
    assert not (_DOMAIN_EXCLUDE & set(domain))
    assert set(domain["expression_conventions"]) == _EXPRESSION_KEYS
    preamble = payload["document_preamble"]
    assert isinstance(preamble, str) and preamble.strip()
    assert "YYYY-MM-DD" not in preamble
    assert "secret fact" not in json.dumps(payload, ensure_ascii=False)
    assert set(payload) <= {
        "ok",
        "command",
        "phase",
        "role",
        "domain",
        "document_preamble",
        "preamble_name_placeholders",
    }


def test_substitute_document_preamble_helpers():
    sys.path.insert(0, str(_BUILD.parent))
    from chapter_write_build_control import substitute_document_preamble

    out = substitute_document_preamble(
        "# {Feature Name}\n**Date:** YYYY-MM-DD\n`{/<cycle_id>/x.md}`\n",
        cycle_id="c1",
        display_name="Widget",
    )
    assert "{Feature Name}" not in out
    assert "Widget" in out
    assert "YYYY-MM-DD" not in out
    assert "<cycle_id>" not in out
    assert "/c1/" in out

    fallback = substitute_document_preamble(
        "# {Topic Name}\n",
        cycle_id="topic-1",
    )
    assert fallback == "# topic-1\n"

    residual = substitute_document_preamble("# {Feature Name}\n", cycle_id="")
    assert residual == "# {Feature Name}\n"

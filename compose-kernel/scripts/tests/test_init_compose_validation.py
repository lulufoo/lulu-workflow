#!/usr/bin/env python3
"""Tests for init_compose_validation.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from init_compose_validation import (  # noqa: E402
    minimal_derive_payload,
    validate_init_artifacts,
    write_minimal_init_work_artifacts,
)
from test_registry_fixtures import first_section_key, minimal_compose_doc_markdown  # noqa: E402
from test_template_data import LEGACY_SECTION_REGISTRY, seed_template_cache  # noqa: E402


def _seed_registry(tmp_path: Path) -> None:
    seed_template_cache(tmp_path, "tech-plan", "tpt_section_registry_url", LEGACY_SECTION_REGISTRY)


@pytest.fixture
def revision_dir(tmp_path: Path) -> Path:
    _seed_registry(tmp_path)
    path = tmp_path / "revision1"
    path.mkdir()
    return path


def test_validate_passes_with_minimal_work_artifacts(revision_dir: Path, tmp_path: Path):
    from section_registry_schema import section_order  # noqa: WPS433

    write_minimal_init_work_artifacts(revision_dir, section_order())
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "tech-plan",
    )
    assert error is None


def test_validate_fails_when_derive_missing(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "tech-plan",
    )
    assert error is not None
    assert "missing derive" in error


def test_validate_fails_on_thin_body(revision_dir: Path, tmp_path: Path):
    from section_registry_schema import section_order  # noqa: WPS433

    write_minimal_init_work_artifacts(revision_dir, section_order())
    key = first_section_key()
    (revision_dir / f"_body-{key}.txt").write_text("Only one line.\n", encoding="utf-8")
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "tech-plan",
    )
    assert error is not None
    assert "thin body" in error


def test_validate_empty_i_star_requires_gaps(revision_dir: Path, tmp_path: Path):
    key = first_section_key()
    payload = minimal_derive_payload(key, i_star="")
    payload["gaps"] = []
    (revision_dir / f"_derive-{key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (revision_dir / f"_body-{key}.txt").write_text("（待补）\n", encoding="utf-8")
    (revision_dir / f"_title-{key}.txt").write_text("（待补）\n", encoding="utf-8")
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "tech-plan",
    )
    assert error is not None
    assert "empty i_star requires at least one gaps entry" in error

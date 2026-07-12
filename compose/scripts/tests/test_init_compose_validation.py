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
    block_h2_above_intent,
    minimal_derive_payload,
    validate_init_artifacts,
    write_minimal_init_work_artifacts,
    write_minimal_partition,
)
from test_registry_fixtures import first_section_key, minimal_compose_doc_markdown  # noqa: E402
from test_template_data import LEGACY_SECTION_REGISTRY, OUTLINE_REGISTRY_FEATURE, seed_template_cache  # noqa: E402


def _seed_registry(tmp_path: Path) -> None:
    seed_template_cache(tmp_path, "lulu-plan", "tpt_section_registry_url", LEGACY_SECTION_REGISTRY)


@pytest.fixture
def revision_dir(tmp_path: Path) -> Path:
    _seed_registry(tmp_path)
    path = tmp_path / "revision1"
    path.mkdir()
    return path


def test_validate_passes_with_minimal_work_artifacts(revision_dir: Path, tmp_path: Path):
    from section_registry_schema import section_order  # noqa: WPS433

    keys = section_order()
    write_minimal_init_work_artifacts(revision_dir, keys)
    write_minimal_partition(revision_dir, keys)
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "lulu-plan",
    )
    assert error is None


def test_validate_fails_when_partition_missing_for_non_inductive(
    revision_dir: Path, tmp_path: Path
):
    from section_registry_schema import section_order  # noqa: WPS433

    write_minimal_init_work_artifacts(revision_dir, section_order())
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "lulu-plan",
    )
    assert error is not None
    assert "missing _partition.json" in error


def test_validate_fails_when_derive_missing(revision_dir: Path, tmp_path: Path):
    from section_registry_schema import section_order  # noqa: WPS433

    write_minimal_partition(revision_dir, section_order())
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "lulu-plan",
    )
    assert error is not None
    assert "missing derive" in error


def test_validate_fails_on_thin_body(revision_dir: Path, tmp_path: Path):
    from section_registry_schema import section_order  # noqa: WPS433

    keys = section_order()
    write_minimal_init_work_artifacts(revision_dir, keys)
    write_minimal_partition(revision_dir, keys)
    key = first_section_key()
    (revision_dir / f"_body-{key}.txt").write_text("Only one line.\n", encoding="utf-8")
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "lulu-plan",
    )
    assert error is not None
    assert "thin body" in error


def test_validate_empty_i_star_requires_gaps(revision_dir: Path, tmp_path: Path):
    from section_registry_schema import section_order  # noqa: WPS433

    write_minimal_partition(revision_dir, section_order())
    key = first_section_key()
    payload = minimal_derive_payload(key, i_star="")
    payload["gaps"] = []
    (revision_dir / f"_derive-{key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (revision_dir / f"_body-{key}.txt").write_text("（待补）\n", encoding="utf-8")
    (revision_dir / "_title-display.json").write_text(
        json.dumps({key: "（待补）"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "lulu-plan",
    )
    assert error is not None
    assert "empty i_star requires at least one gaps entry" in error


@pytest.mark.parametrize(
    "bad_title",
    [
        "见 frontend/js/main.js",  # code path token
        "调用 archive_document()",  # API/symbol token
        "这是一整句被误当作标题的正文说明其长度远远超过了四十个全角字符的上限用来触发过长的硬性校验规则确保它一定会失败",  # too long
    ],
)
def test_validate_fails_on_bad_display_title(
    revision_dir: Path, tmp_path: Path, bad_title: str
):
    from section_registry_schema import section_order  # noqa: WPS433

    keys = section_order()
    write_minimal_init_work_artifacts(revision_dir, keys)
    write_minimal_partition(revision_dir, keys)
    key = first_section_key()
    payload = minimal_derive_payload(key)
    payload["display_title"] = bad_title
    (revision_dir / f"_derive-{key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(revision_dir, compose_doc, tmp_path, "lulu-plan")
    assert error is not None
    assert "display_title" in error


def test_validate_fails_when_display_title_reuses_heading(revision_dir: Path, tmp_path: Path):
    from init_compose_validation import section_headings_for_profile  # noqa: WPS433
    from section_registry_schema import section_order  # noqa: WPS433

    keys = section_order()
    write_minimal_init_work_artifacts(revision_dir, keys)
    write_minimal_partition(revision_dir, keys)
    key = first_section_key()
    heading = section_headings_for_profile(tmp_path, "lulu-plan")[key]
    payload = minimal_derive_payload(key)
    payload["display_title"] = heading
    (revision_dir / f"_derive-{key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(revision_dir, compose_doc, tmp_path, "lulu-plan")
    assert error is not None
    assert "must not reuse the registry heading" in error


def test_validate_fails_on_display_title_drift(revision_dir: Path, tmp_path: Path):
    """_title-display.json diverging from derive display_title (e.g. manual edit) fails."""
    from section_registry_schema import section_order  # noqa: WPS433

    keys = section_order()
    write_minimal_init_work_artifacts(revision_dir, keys)
    write_minimal_partition(revision_dir, keys)
    key = first_section_key()
    display_path = revision_dir / "_title-display.json"
    data = json.loads(display_path.read_text(encoding="utf-8"))
    data[key] = "漂移标题"
    display_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(revision_dir, compose_doc, tmp_path, "lulu-plan")
    assert error is not None
    assert "_title-display.json" in error


def test_validate_fails_when_display_title_missing(revision_dir: Path, tmp_path: Path):
    from section_registry_schema import section_order  # noqa: WPS433

    keys = section_order()
    write_minimal_init_work_artifacts(revision_dir, keys)
    write_minimal_partition(revision_dir, keys)
    key = first_section_key()
    payload = minimal_derive_payload(key)
    del payload["display_title"]
    (revision_dir / f"_derive-{key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    compose_doc = revision_dir / "tech-doc.md"
    compose_doc.write_text(minimal_compose_doc_markdown(), encoding="utf-8")

    error = validate_init_artifacts(revision_dir, compose_doc, tmp_path, "lulu-plan")
    assert error is not None
    assert "display_title" in error


def test_block_h2_above_intent_finds_nearest_h2():
    doc = "## Overview\n\n### 现状 <!-- section-key:CTX -->\nBody.\n"
    assert block_h2_above_intent(doc, "CTX") == "Overview"


def test_validate_block_titles_when_outline_present(revision_dir: Path, tmp_path: Path):
    minimal_outline = {
        "version": "1",
        "$schema_id": "outline-schema",
        "outline_order": ["OV"],
        "blocks": {"OV": OUTLINE_REGISTRY_FEATURE["blocks"]["OV"]},
    }
    minimal_section_registry = {
        "version": "1",
        "section_order": ["CTX", "GO"],
        "document_preamble": "# Test\n\n",
        "sections": {
            "CTX": {"heading": "Context", "intent": "x"},
            "GO": {"heading": "Goal", "intent": "x"},
        },
    }
    seed_template_cache(
        tmp_path,
        "lulu-design",
        "tdt_outline_registry_url",
        minimal_outline,
    )
    seed_template_cache(
        tmp_path,
        "lulu-design",
        "tdt_section_registry_url",
        minimal_section_registry,
    )
    from compose_doc_control import append_intent, init_doc, patch_block_heading  # noqa: WPS433

    compose_doc = revision_dir / "design-doc.md"
    init_doc(compose_doc, preamble="# Feature\n\n")
    write_minimal_init_work_artifacts(revision_dir, ["CTX", "GO"])
    (revision_dir / "_title-block.json").write_text(
        json.dumps({"OV": "1. 问题与目标"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # H3 must equal derive display_title (single SoT) — reuse the fixture titles.
    ctx_title = minimal_derive_payload("CTX")["display_title"]
    go_title = minimal_derive_payload("GO")["display_title"]
    append_intent(
        compose_doc,
        section_key="CTX",
        display_title=ctx_title,
        body="Context.",
        outline=minimal_outline,
    )
    append_intent(
        compose_doc,
        section_key="GO",
        display_title=go_title,
        body="Goal.",
        outline=minimal_outline,
    )
    patch_block_heading(
        compose_doc,
        block_key="OV",
        title="1. 问题与目标",
        outline=minimal_outline,
    )

    error = validate_init_artifacts(
        revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None

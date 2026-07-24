#!/usr/bin/env python3
"""Tests for domain_instance_schema expression_conventions string|object normalize."""

from __future__ import annotations

import json
from pathlib import Path

from domain_instance_schema import (  # noqa: E402
    load_and_validate_domain_instance,
    normalize_expression_conventions,
    validate_domain_instance,
)
from framework_template_sources import tech_arch_topic_domain_instance  # noqa: E402
from scope_resolver import resolve_domain_markdown  # noqa: E402


def _base_domain(**overrides: object) -> dict:
    data = {
        "version": "1",
        "$schema_id": "domain-schema",
        "cycle_type": "topic",
        "domain_id": "test_domain",
        "cognitive_frame": "frame",
        "expression_conventions": "analytical prose",
        "intent_anchor": "anchor",
        "audience_type": "audience",
    }
    data.update(overrides)
    return data


class TestExpressionConventionsValidate:
    def test_string_ok(self):
        assert validate_domain_instance(_base_domain()) == []

    def test_object_four_keys_ok(self):
        data = _base_domain(
            expression_conventions={
                "register": "r",
                "carriers": "c",
                "scannability": "s",
                "altitude": "a",
            },
        )
        assert validate_domain_instance(data) == []

    def test_object_missing_key(self):
        data = _base_domain(
            expression_conventions={
                "register": "r",
                "carriers": "c",
                "scannability": "s",
            },
        )
        errors = validate_domain_instance(data)
        assert any("missing keys" in err for err in errors)

    def test_object_extra_key(self):
        data = _base_domain(
            expression_conventions={
                "register": "r",
                "carriers": "c",
                "scannability": "s",
                "altitude": "a",
                "grounding": "g",
            },
        )
        errors = validate_domain_instance(data)
        assert any("unexpected keys" in err for err in errors)

    def test_empty_string_rejected(self):
        errors = validate_domain_instance(_base_domain(expression_conventions="  "))
        assert any("expression_conventions" in err for err in errors)


class TestExpressionConventionsNormalize:
    def test_string_passthrough(self):
        assert normalize_expression_conventions("keep me") == "keep me"

    def test_object_multiline_labeled(self):
        text = normalize_expression_conventions(
            {
                "register": "r",
                "carriers": "c",
                "scannability": "s",
                "altitude": "a",
            },
        )
        assert text == (
            "register: r\n"
            "carriers: c\n"
            "scannability: s\n"
            "altitude: a"
        )


class TestLoadAndResolve:
    def test_arch_framework_object_loads_as_string(self, tmp_path: Path):
        path = tmp_path / "domain.json"
        payload = tech_arch_topic_domain_instance()
        assert isinstance(payload["expression_conventions"], dict)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        loaded = load_and_validate_domain_instance("topic", path=path)
        ec = loaded["expression_conventions"]
        assert isinstance(ec, str)
        assert ec.startswith("register: ")
        assert "\ncarriers: " in ec
        assert "\nscannability: " in ec
        assert "\naltitude: " in ec
        assert "decision-doc" not in ec

    def test_resolve_domain_markdown_field_is_string(self, tmp_path: Path):
        path = tmp_path / "domain.json"
        path.write_text(
            json.dumps(tech_arch_topic_domain_instance(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        md = resolve_domain_markdown(
            cycle_type="topic",
            domain_instance_path=path,
        )
        # Extract JSON fence
        start = md.index("```json") + len("```json")
        end = md.index("```", start)
        data = json.loads(md[start:end])
        assert isinstance(data["expression_conventions"], str)
        assert data["expression_conventions"].startswith("register: ")

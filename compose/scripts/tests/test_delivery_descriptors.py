#!/usr/bin/env python3
"""Tests for delivery_descriptors manifest."""

from __future__ import annotations

import bootstrap  # noqa: F401
from delivery_descriptors import (  # noqa: E402
    _compose_descriptor,
    delivery_index_deliver_facts,
    iter_delivery_descriptors,
)


def test_iter_delivery_includes_decision_holders_from_manifest():
    stages = {d.stage_name for d in iter_delivery_descriptors()}
    assert "lulu-bet" in stages
    assert "lulu-approach" in stages
    assert "lulu-arch" in stages
    assert "lulu-design" in stages
    assert "lulu-plan" in stages
    assert "lulu-spec" in stages


def test_compose_descriptor_design_deliver_facts_from_profile():
    desc = _compose_descriptor("lulu-design")
    assert desc is not None
    assert desc.deliver_facts is True


def test_compose_descriptor_plan_does_not_deliver_facts():
    desc = _compose_descriptor("lulu-plan")
    assert desc is not None
    assert desc.deliver_facts is False


def test_delivery_index_deliver_facts_requires_json_true():
    assert delivery_index_deliver_facts({"deliver_facts": True}) is True
    assert delivery_index_deliver_facts({"deliver_facts": False}) is False
    assert delivery_index_deliver_facts({"deliver_facts": "false"}) is False
    assert delivery_index_deliver_facts({}) is False
    assert delivery_index_deliver_facts(None) is False

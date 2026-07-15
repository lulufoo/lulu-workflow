#!/usr/bin/env python3
"""Test helpers derived from section registry (no hardcoded section names)."""

from __future__ import annotations

from section_registry_schema import section_heading, section_order


def section_headings_map() -> dict[str, str]:
    order = section_order()
    return {key: section_heading(key) for key in order}


def section_key_at(index: int) -> str:
    return section_order()[index]


def first_section_key() -> str:
    return section_order()[0]


def second_section_key() -> str:
    return section_order()[1]


def third_section_key() -> str:
    return section_order()[2]


def last_section_key() -> str:
    return section_order()[-1]


def fourth_section_key() -> str:
    return section_order()[3]


def fifth_section_key() -> str:
    return section_order()[4]

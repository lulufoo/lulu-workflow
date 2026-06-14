#!/usr/bin/env python3
"""Tests for section_pointer_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from section_pointer_schema import (  # noqa: E402
    advance_section,
    all_sections_stable,
    init_section_pointer,
    mark_section_stable,
    next_probe_seq,
    rewind_section,
    save_section_pointer,
    section_pointer_path,
    update_latest_probe,
    validate_section_pointer,
)
from test_registry_fixtures import (  # noqa: E402
    first_section_key,
    fourth_section_key,
    second_section_key,
    third_section_key,
)


def test_init_pointer_first_section_active():
    first = first_section_key()
    second = second_section_key()
    pointer = init_section_pointer(round_n=1, revision=1, cycle_id="c1")
    assert pointer["active_section"] == first
    assert pointer["sections"][first]["status"] == "active"
    assert pointer["sections"][second]["status"] == "pending"
    assert validate_section_pointer(pointer) == []


def test_advance_section_moves_active():
    first = first_section_key()
    second = second_section_key()
    pointer = init_section_pointer(round_n=1, revision=1, cycle_id="c1")
    pointer = update_latest_probe(pointer, section_key=first, probe_seq=1)
    pointer = mark_section_stable(pointer, first)
    advanced = advance_section(pointer)
    assert advanced["sections"][first]["status"] == "stable"
    assert advanced["active_section"] == second
    assert advanced["sections"][second]["status"] == "active"


def test_rewind_invalidates_downstream():
    first = first_section_key()
    second = second_section_key()
    fourth = fourth_section_key()
    pointer = init_section_pointer(round_n=1, revision=1, cycle_id="c1")
    for key in (first, second, third_section_key()):
        pointer = update_latest_probe(pointer, section_key=key, probe_seq=1)
        pointer = mark_section_stable(pointer, key)
        pointer = advance_section(pointer)
    assert pointer["active_section"] == fourth
    rewound = rewind_section(pointer, to_section=first, reason="user edit")
    assert rewound["active_section"] == first
    assert rewound["sections"][first]["status"] == "active"
    assert rewound["sections"][second]["status"] == "invalidated"
    assert rewound["sections"][fourth]["status"] == "invalidated"
    assert rewound["sections"][second]["invalidated_from"] == first


def test_all_sections_stable_false_until_complete():
    first = first_section_key()
    pointer = init_section_pointer(round_n=1, revision=1, cycle_id="c1")
    assert all_sections_stable(pointer) is False
    pointer = mark_section_stable(pointer, first)
    assert all_sections_stable(pointer) is False


def test_save_and_load_pointer(tmp_path: Path):
    pointer = init_section_pointer(round_n=2, revision=1, cycle_id="c1")
    path = section_pointer_path(tmp_path, 2)
    save_section_pointer(path, pointer)
    assert path.exists()


def test_next_probe_seq_increments():
    first = first_section_key()
    pointer = init_section_pointer(round_n=1, revision=1, cycle_id="c1")
    assert next_probe_seq(pointer, first) == 1
    pointer = update_latest_probe(pointer, section_key=first, probe_seq=1)
    assert next_probe_seq(pointer, first) == 2

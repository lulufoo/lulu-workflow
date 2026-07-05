#!/usr/bin/env python3
"""Shared scope-ref selection helpers for StartAdapter implementations."""

from __future__ import annotations

from pathlib import Path

from delivered_refs_schema import (
    DeliveredRef,
    entry_path_ok,
    load_delivered_refs_file,
)


def infer_product_or_tech(cycle_id: str, project_root: Path) -> str:
    """Return ``product`` when cycle delivered-refs has a valid lulu-spec entry, else ``tech``."""
    data = load_delivered_refs_file(cycle_id, project_root)
    if entry_path_ok(data, "lulu-spec"):
        return "product"
    return "tech"


def first_ref(refs: list[DeliveredRef], delivered_type: str) -> DeliveredRef | None:
    for ref in refs:
        if ref.type == delivered_type:
            return ref
    return None

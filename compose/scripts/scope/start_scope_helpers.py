#!/usr/bin/env python3
"""Shared scope-ref selection helpers for StartAdapter implementations."""

from __future__ import annotations

from delivered_refs_schema import (
    DeliveredRef,
)


def first_ref(refs: list[DeliveredRef], delivered_type: str) -> DeliveredRef | None:
    for ref in refs:
        if ref.type == delivered_type:
            return ref
    return None

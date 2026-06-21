#!/usr/bin/env python3
"""product-spec StartAdapter implementation."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from delivered_refs_schema import (  # noqa: E402
    DeliveredRef,
    entry_path_ok,
    load_delivered_refs_file,
    parse_delivered_refs,
    ref_from_file_entry,
)
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_state_schema import load_workflow_state  # noqa: E402
from compose_session import workflow_state_path  # noqa: E402


class ProductSpecStartAdapter:
    """Start rules for product-spec compose profile (feature cycles only)."""

    def validate_for_start(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
        carry_forward_ref: str = "",
    ) -> list[str]:
        del run_mode, carry_forward_ref
        if detect_cycle_type(cycle_id) != "feature":
            return ["product-spec is feature-only; topic cycles are not supported"]
        data = load_delivered_refs_file(cycle_id, project_root)
        if not entry_path_ok(data, "product-diagnostic"):
            return ["missing delivered-refs entry: product-diagnostic"]
        return []

    def resolve_delivered_refs(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
    ) -> list[DeliveredRef]:
        del run_mode
        data = load_delivered_refs_file(cycle_id, project_root)
        ref = ref_from_file_entry("product-diagnostic", data)
        if ref is None or not Path(ref.path).is_file():
            return []
        return [ref]

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        ws_path = workflow_state_path(cycle_id, project_root, "product-spec")
        for ref in parse_delivered_refs(load_workflow_state(ws_path)):
            if ref.type == "product-diagnostic":
                return ref
        return None

"""Profile-driven upstream SSOT resolution for compose read-context."""

from __future__ import annotations

from pathlib import Path

from delivered_refs_schema import DeliveredRef
from workflow_paths import load_profile


def _first_ref_by_type(refs: list[DeliveredRef], ref_type: str) -> DeliveredRef | None:
    for ref in refs:
        if ref.type == ref_type:
            return ref
    return None


def supplementary_ref_specs(profile_id: str) -> list[dict[str, str]]:
    profile = load_profile(profile_id)
    upstream = profile.get("upstream_ssot") or {}
    raw = upstream.get("supplementary_refs") or []
    if not isinstance(raw, list):
        return []
    specs: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref_type = str(item.get("type", "")).strip()
        ctx_key = str(item.get("ctx_key", "")).strip()
        if ref_type and ctx_key:
            specs.append({"type": ref_type, "ctx_key": ctx_key})
    return specs


def resolve_supplementary_paths(
    profile_id: str,
    scope_refs: list[DeliveredRef],
    delivered_refs: list[DeliveredRef],
) -> dict[str, str]:
    """Map ctx_key -> absolute path for profile supplementary_refs declarations."""
    result: dict[str, str] = {}
    scope_tail = scope_refs[1:] if len(scope_refs) > 1 else []
    for spec in supplementary_ref_specs(profile_id):
        ref_type = spec["type"]
        ctx_key = spec["ctx_key"]
        found = _first_ref_by_type(scope_tail, ref_type) or _first_ref_by_type(
            delivered_refs,
            ref_type,
        )
        if found is not None:
            result[ctx_key] = str(Path(found.path).resolve())
    return result

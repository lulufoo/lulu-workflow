#!/usr/bin/env python3
"""Op-list disposition-review patch validate/apply (archive-6.0 Confirm).

Patch shape (JSON):
  {
    "version": "1",
    "counts": {"carried": int, "quarantined": int, "not_needed": int},  # optional
    "cohorts": [...],  # optional review metadata
    "ops": [
      {"op": "promote", "fact_id": "F-n", "lens_tags": ["L", ...], "note"?: str},
      {"op": "demote", "fact_id": "F-n",
       "disposition": "quarantined"|"not_needed", "rule_id"?: str, "note"?: str},
      {"op": "retag", "fact_id": "F-n", "lens_tags": ["L", ...], "note"?: str},
      {"op": "escalate", "fact_id": "F-n", "note"?: str}
    ]
  }
"""

from __future__ import annotations

from typing import Any

from facts_schema import (
    DERIVATION_DISPOSITIONS,
    fact_disposition,
    normalize_fact,
    single_lens_error,
    validate_facts,
)

PATCH_OPS = frozenset({"promote", "demote", "retag", "escalate"})
DEMOTE_DISPOSITIONS = frozenset({"quarantined", "not_needed"})


def validate_disposition_patch(
    patch: Any,
    facts: list[dict[str, Any]],
    *,
    allowed_lenses: list[str] | None = None,
    allowed_rule_ids: list[str] | None = None,
    single_lens: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(patch, dict):
        return ["patch root must be an object"]
    if patch.get("version") != "1":
        errors.append("patch.version must be '1'")
    ops = patch.get("ops")
    if not isinstance(ops, list):
        errors.append("patch.ops must be an array")
        return errors
    if not ops:
        errors.append("patch.ops must be a non-empty array")
        return errors

    by_id = {str(f.get("id", "")).strip(): f for f in facts if isinstance(f, dict)}
    counts = patch.get("counts")
    if counts is not None:
        if not isinstance(counts, dict):
            errors.append("patch.counts must be an object when present")
        else:
            for key in ("carried", "quarantined", "not_needed"):
                if key in counts and not isinstance(counts[key], int):
                    errors.append(f"patch.counts.{key} must be an int when present")
            extra = set(counts) - {"carried", "quarantined", "not_needed"}
            if extra:
                errors.append(f"patch.counts unexpected fields {sorted(extra)}")

    cohorts = patch.get("cohorts")
    if cohorts is not None and not isinstance(cohorts, list):
        errors.append("patch.cohorts must be an array when present")

    for index, op in enumerate(ops):
        prefix = f"ops[{index}]"
        if not isinstance(op, dict):
            errors.append(f"{prefix} must be an object")
            continue
        kind = str(op.get("op", "")).strip().lower()
        if kind not in PATCH_OPS:
            errors.append(f"{prefix}.op must be one of {sorted(PATCH_OPS)}")
            continue
        fact_id = op.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id.strip():
            errors.append(f"{prefix}.fact_id must be a non-empty string")
            continue
        fid = fact_id.strip()
        if fid not in by_id:
            errors.append(f"{prefix}.fact_id {fid!r} not in facts")
            continue
        note = op.get("note")
        if note is not None and (not isinstance(note, str) or not note.strip()):
            errors.append(f"{prefix}.note must be a non-empty string when present")

        if kind in ("promote", "retag"):
            tags = op.get("lens_tags")
            if not isinstance(tags, list) or not tags:
                errors.append(f"{prefix}.lens_tags must be a non-empty array")
            else:
                message = single_lens_error(prefix, tags) if single_lens else None
                if message:
                    errors.append(message)
                for t_i, tag in enumerate(tags):
                    if not isinstance(tag, str) or not tag.strip():
                        errors.append(
                            f"{prefix}.lens_tags[{t_i}] must be a non-empty string",
                        )
                    elif allowed_lenses is not None:
                        key = tag.strip().upper()
                        allowed = {
                            l.strip().upper() for l in allowed_lenses if str(l).strip()
                        }
                        if key not in allowed:
                            errors.append(
                                f"{prefix}.lens_tags[{t_i}] {key!r} not in "
                                f"allowed lenses {sorted(allowed)}",
                            )
            allowed_keys = {"op", "fact_id", "lens_tags", "note"}
        elif kind == "demote":
            disposition = str(op.get("disposition", "")).strip().lower()
            if disposition not in DEMOTE_DISPOSITIONS:
                errors.append(
                    f"{prefix}.disposition must be one of "
                    f"{sorted(DEMOTE_DISPOSITIONS)}",
                )
            if disposition == "not_needed":
                rule_id = op.get("rule_id")
                if not isinstance(rule_id, str) or not rule_id.strip():
                    errors.append(
                        f"{prefix}.rule_id required when disposition=not_needed",
                    )
                elif allowed_rule_ids is not None and rule_id.strip() not in {
                    r.strip() for r in allowed_rule_ids if str(r).strip()
                }:
                    errors.append(
                        f"{prefix}.rule_id {rule_id.strip()!r} not in "
                        f"consume_policy.rules {sorted(allowed_rule_ids)}",
                    )
            allowed_keys = {"op", "fact_id", "disposition", "rule_id", "note"}
        else:  # escalate
            allowed_keys = {"op", "fact_id", "note"}
        extra = set(op) - allowed_keys
        if extra:
            errors.append(f"{prefix} unexpected fields {sorted(extra)}")

    extra_top = set(patch) - {"version", "counts", "cohorts", "ops", "appendix_ids"}
    if extra_top:
        errors.append(f"patch unexpected fields {sorted(extra_top)}")

    if errors:
        return errors

    # Dry-run apply into a copy and schema-validate.
    try:
        preview = apply_disposition_patch(facts, patch, mutate=False)
    except ValueError as exc:
        return [str(exc)]
    errors.extend(
        validate_facts(
            preview,
            allowed_lenses=allowed_lenses,
            allowed_rule_ids=allowed_rule_ids,
        )
    )
    return errors


def apply_disposition_patch(
    facts: list[dict[str, Any]],
    patch: dict[str, Any],
    *,
    mutate: bool = True,
) -> list[dict[str, Any]]:
    """Apply ops; return resulting facts list (normalized)."""
    working = [dict(f) for f in facts]
    by_index = {str(f.get("id", "")).strip(): i for i, f in enumerate(working)}
    for op in patch.get("ops") or []:
        kind = str(op.get("op", "")).strip().lower()
        fid = str(op.get("fact_id", "")).strip()
        if fid not in by_index:
            raise ValueError(f"fact_id not found during apply: {fid!r}")
        entry = dict(working[by_index[fid]])
        derivation = dict(entry.get("derivation") or {})
        upstream = derivation.get("upstream_ref")
        if not isinstance(upstream, list) or not upstream:
            raise ValueError(
                f"{fid}: promote/demote/retag require existing non-empty "
                "derivation.upstream_ref",
            )

        if kind == "promote":
            tags = [str(t).strip().upper() for t in op["lens_tags"]]
            entry["lens_tags"] = tags
            entry["derivation"] = {
                "disposition": "carried",
                "upstream_ref": [str(r).strip() for r in upstream],
            }
        elif kind == "retag":
            if fact_disposition(entry) != "carried":
                raise ValueError(f"{fid}: retag requires disposition=carried")
            entry["lens_tags"] = [str(t).strip().upper() for t in op["lens_tags"]]
            entry["derivation"] = {
                "disposition": "carried",
                "upstream_ref": [str(r).strip() for r in upstream],
            }
        elif kind == "demote":
            disposition = str(op["disposition"]).strip().lower()
            entry["lens_tags"] = []
            new_derivation: dict[str, Any] = {
                "disposition": disposition,
                "upstream_ref": [str(r).strip() for r in upstream],
            }
            if disposition == "not_needed":
                new_derivation["rule_id"] = str(op["rule_id"]).strip()
            entry["derivation"] = new_derivation
        elif kind == "escalate":
            # Metadata-only for Confirm; facts unchanged.
            pass
        else:
            raise ValueError(f"unknown op: {kind!r}")

        if kind != "escalate":
            working[by_index[fid]] = normalize_fact(entry)

    if mutate:
        facts[:] = working
    return working


def disposition_counts(facts: list[dict[str, Any]]) -> dict[str, int]:
    counts = {d: 0 for d in sorted(DERIVATION_DISPOSITIONS)}
    for fact in facts:
        disposition = fact_disposition(fact)
        if disposition in counts:
            counts[disposition] += 1
    return counts

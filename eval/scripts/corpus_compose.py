#!/usr/bin/env python3
"""Compose EvalCorpus documents from dimension stamps."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from corpus_schema import corpus_ref, validate_corpus

COMPOSED_CORPUS_ID = "tech-plan-composed"
COMPOSED_CORPUS_VERSION = "1"
COMPOSED_CORPUS_REF = f"{COMPOSED_CORPUS_ID}@{COMPOSED_CORPUS_VERSION}"


def corpus_fingerprint(
    dimension_ids: list[str],
    *,
    cycle_type: str = "feature",
) -> str:
    """Return stable short hash for cycle_type + dimension id set."""
    payload = f"{cycle_type}:{','.join(sorted(dimension_ids))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_dimension_stamp(path: Path) -> dict[str, Any]:
    """Load one dimension stamp JSON object."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"stamp must be an object: {path}")
    if not data.get("id"):
        raise ValueError(f"stamp missing id: {path}")
    return data


def assign_review_sequences(dimensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Renumber review.seq and output_path suffix 1..n in dispatch order."""
    result: list[dict[str, Any]] = []
    for index, dim in enumerate(dimensions, start=1):
        item = copy.deepcopy(dim)
        review = dict(item.get("review") or {})
        review["seq"] = index
        review["output_path"] = f"tech-review-e{{M}}{index}.md"
        if "template" not in review:
            review["template"] = "eval/review.template.md"
        item["review"] = review
        result.append(item)
    return result


def compose_corpus(
    *,
    corpus_id: str,
    corpus_version: str,
    scope: str,
    dimensions: list[dict[str, Any]],
    dimension_dispatch: str = "parallel",
    context: str = "offline",
) -> dict[str, Any]:
    """Build and validate a full EvalCorpus dict."""
    if not dimensions:
        raise ValueError("dimensions must be non-empty")
    data: dict[str, Any] = {
        "id": corpus_id,
        "version": corpus_version,
        "scope": scope,
        "context": context,
        "dimension_dispatch": dimension_dispatch,
        "dimensions": assign_review_sequences(dimensions),
    }
    errors = validate_corpus(data)
    if errors:
        raise ValueError(f"composed corpus invalid: {'; '.join(errors)}")
    if corpus_ref(data) != f"{corpus_id}@{corpus_version}":
        raise ValueError("corpus_id/version mismatch after compose")
    return data


def is_composed_corpus_ref(ref: str) -> bool:
    """Return True when ref points at the dynamic tech-plan composed corpus."""
    return ref == COMPOSED_CORPUS_REF

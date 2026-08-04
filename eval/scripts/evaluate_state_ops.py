#!/usr/bin/env python3
"""evaluate-state helpers that combine schema I/O with EvalCorpus binding."""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import Any

from corpus_compose import corpus_fingerprint, is_composed_corpus_ref
from corpus_schema import (
    corpus_ref,
    dispatch_ids,
    dispatch_legacy_aliases,
    resolve_dim_id,
)
from evaluate_state_schema import (
    build_initial_evaluate_state,
    merge_dimension_status,
    parse_frontmatter_fields,
    save_evaluate_state,
    validate_evaluate_state,
)


def dispatch_dims_for_corpus(corpus: dict[str, Any]) -> list[str]:
    """Return canonical dimension ids for a corpus document."""
    return dispatch_ids(corpus)


def dispatch_legacy_for_corpus(corpus: dict[str, Any]) -> list[str]:
    """Return legacy dispatch aliases (e1/e2/e3) for a corpus document."""
    return dispatch_legacy_aliases(corpus)


def build_initial_evaluate_state_for_corpus(
    corpus: dict[str, Any],
    *,
    cycle_type: str = "feature",
    evaluate_round: int | None = None,
    focus_l: str = "",
) -> dict[str, str]:
    """Return v3 frontmatter for a new evaluate-state from an EvalCorpus."""
    ids = dispatch_ids(corpus)
    ref = corpus_ref(corpus)
    fingerprint = ""
    if is_composed_corpus_ref(ref):
        fingerprint = corpus_fingerprint(ids, cycle_type=cycle_type)
    return build_initial_evaluate_state(
        dimension_ids=ids,
        corpus_ref=ref,
        corpus_fingerprint=fingerprint,
        dimension_dispatch=str(corpus.get("dimension_dispatch", "parallel")),
        evaluate_round=evaluate_round,
        focus_l=focus_l,
    )


def init_evaluate_state_for_corpus(
    path: Path,
    corpus: dict[str, Any],
    *,
    cycle_type: str = "feature",
    evaluate_round: int | None = None,
    focus_l: str = "",
) -> None:
    """Initialize evaluate-state.md v3 from a resolved EvalCorpus."""
    save_evaluate_state(
        path,
        build_initial_evaluate_state_for_corpus(
            corpus,
            cycle_type=cycle_type,
            evaluate_round=evaluate_round,
            focus_l=focus_l,
        ),
        merge=False,
    )


def _resolve_dim_key(
    data: dict[str, str],
    dim: str,
    *,
    corpus: dict[str, Any] | None = None,
) -> str:
    if corpus is None:
        if not data.get("corpus_ref", ""):
            return dim
        raise ValueError(
            "resolve dimension: explicit corpus required when evaluate-state has corpus_ref",
        )
    return resolve_dim_id(corpus, dim)


def merge_current_dimension(
    data: dict[str, str],
    dim: str,
    status: str,
    *,
    corpus: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Patch dimension status; dim may be legacy alias or canonical id."""
    dim_id = _resolve_dim_key(data, dim, corpus=corpus)
    return merge_dimension_status(data, dim_id, status)


def dimension_status_legacy_map(
    eval_data: dict[str, str],
    *,
    corpus: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Return dimension status keyed by legacy alias for tests / display."""
    from evaluate_state_schema import parse_dimension_status

    canonical = parse_dimension_status(eval_data.get("dimension_status", "{}"))
    if corpus is None:
        if not eval_data.get("corpus_ref", ""):
            return canonical
        raise ValueError(
            "legacy dimension map: explicit corpus required when evaluate-state has corpus_ref",
        )
    result: dict[str, str] = {}
    for dim in corpus["dimensions"]:
        alias = str(dim.get("legacy_alias") or dim["id"])
        dim_id = str(dim["id"])
        result[alias] = canonical.get(dim_id, "pending")
    return result


def save_evaluate_state_locked(
    path: Path,
    patch_fn,
) -> dict[str, str]:
    """Read-merge-validate-write evaluate-state under file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                existing = parse_frontmatter_fields(
                    path.read_text(encoding="utf-8"),
                )
                data = patch_fn(dict(existing))
            else:
                data = patch_fn({})

            errors = validate_evaluate_state(data)
            if errors:
                raise ValueError(
                    f"evaluate-state data invalid: {'; '.join(errors)}",
                )
            save_evaluate_state(path, data, merge=False)
            return data
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

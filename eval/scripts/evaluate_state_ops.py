#!/usr/bin/env python3
"""evaluate-state helpers that combine schema I/O with EvalCorpus binding."""

from __future__ import annotations

import fcntl
from pathlib import Path

from corpus_schema import (
    corpus_ref,
    dispatch_ids,
    dispatch_legacy_aliases,
    load_corpus_by_ref,
    resolve_dim_id,
)
from evaluate_state_schema import (
    build_initial_evaluate_state,
    load_evaluate_state,
    merge_dimension_status,
    parse_frontmatter_fields,
    save_evaluate_state,
    validate_evaluate_state,
)

_VALID_MODES = frozenset({"product", "tech"})


def dispatch_dims_for_corpus_ref(corpus_ref_str: str) -> list[str]:
    """Return canonical dimension ids for a corpus reference."""
    corpus = load_corpus_by_ref(corpus_ref_str)
    return dispatch_ids(corpus)


def dispatch_legacy_for_corpus_ref(corpus_ref_str: str) -> list[str]:
    """Return legacy dispatch aliases (e1/e2/e3) for a corpus reference."""
    corpus = load_corpus_by_ref(corpus_ref_str)
    return dispatch_legacy_aliases(corpus)


def dispatch_dims_for_mode(*, mode: str, corpus_ref_for_mode) -> list[str]:
    """Return canonical dimension ids for workflow mode."""
    return dispatch_dims_for_corpus_ref(corpus_ref_for_mode(mode))


def dispatch_legacy_for_mode(*, mode: str, corpus_ref_for_mode) -> list[str]:
    """Return legacy aliases for workflow mode."""
    return dispatch_legacy_for_corpus_ref(corpus_ref_for_mode(mode))


def build_initial_evaluate_state_for_mode(
    *,
    mode: str,
    corpus_ref_for_mode,
) -> dict[str, str]:
    """Return v3 frontmatter for a new evaluate-state from workflow mode."""
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode!r} (allowed: {sorted(_VALID_MODES)})")
    ref = corpus_ref_for_mode(mode)
    corpus = load_corpus_by_ref(ref)
    return build_initial_evaluate_state(
        dimension_ids=dispatch_ids(corpus),
        corpus_ref=corpus_ref(corpus),
        dimension_dispatch=str(corpus.get("dimension_dispatch", "parallel")),
    )


def init_evaluate_state(
    path: Path,
    *,
    mode: str,
    corpus_ref_for_mode,
) -> None:
    """Initialize evaluate-state.md v3 for workflow mode."""
    save_evaluate_state(
        path,
        build_initial_evaluate_state_for_mode(
            mode=mode,
            corpus_ref_for_mode=corpus_ref_for_mode,
        ),
        merge=False,
    )


def _resolve_dim_key(data: dict[str, str], dim: str) -> str:
    ref = data.get("corpus_ref", "")
    if not ref:
        return dim
    corpus = load_corpus_by_ref(ref)
    return resolve_dim_id(corpus, dim)


def merge_current_dimension(
    data: dict[str, str],
    dim: str,
    status: str,
) -> dict[str, str]:
    """Patch dimension status; dim may be legacy alias or canonical id."""
    dim_id = _resolve_dim_key(data, dim)
    return merge_dimension_status(data, dim_id, status)


def dimension_status_legacy_map(eval_data: dict[str, str]) -> dict[str, str]:
    """Return dimension status keyed by legacy alias for tests / display."""
    from evaluate_state_schema import parse_dimension_status

    canonical = parse_dimension_status(eval_data.get("dimension_status", "{}"))
    ref = eval_data.get("corpus_ref", "")
    if not ref:
        return canonical
    corpus = load_corpus_by_ref(ref)
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

#!/usr/bin/env python3
"""EvalCorpus schema, validation, and bind expansion.

CLI:
    python3 corpus_schema.py --schema
    python3 corpus_schema.py --validate --path <corpus.json>
    python3 corpus_schema.py --expand --path <corpus.json> --bind bind.json
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCHEMA: dict[str, Any] = {
    "version": "3",
    "required_top_level": [
        "id",
        "version",
        "scope",
        "context",
        "dimension_dispatch",
        "dimensions",
    ],
    "enums": {
        "context": ["offline"],
        "dimension_dispatch": ["parallel", "serial"],
        "sot_kind": ["url", "codebase"],
        "sot_role": ["primary", "supplementary", "constraint"],
        "method_kind": ["builtin", "external"],
        "codebase_strategy": ["all"],
    },
    "bind_placeholders": [
        "tech_doc",
        "product_ref",
        "cycle_type",
        "M",
        "ptc_url",
        "tpt_intent_eval_framework_url",
    ],
}

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
_VALID_SOT_KIND = frozenset(_SCHEMA["enums"]["sot_kind"])
_VALID_SOT_ROLE = frozenset(_SCHEMA["enums"]["sot_role"])
_VALID_METHOD_KIND = frozenset(_SCHEMA["enums"]["method_kind"])
_VALID_CONTEXT = frozenset(_SCHEMA["enums"]["context"])
_VALID_DISPATCH = frozenset(_SCHEMA["enums"]["dimension_dispatch"])
_VALID_CODEBASE_STRATEGY = frozenset(_SCHEMA["enums"]["codebase_strategy"])


def get_schema() -> dict[str, Any]:
    """Return EvalCorpus schema dict."""
    return copy.deepcopy(_SCHEMA)


def load_corpus(path: Path) -> dict[str, Any]:
    """Load corpus JSON from path."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"corpus root must be an object: {path}")
    return data


def _require_str(obj: dict[str, Any], key: str, errors: list[str], *, ctx: str) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{ctx}: missing or invalid string field '{key}'")


def _validate_sot(sot: Any, errors: list[str], *, ctx: str) -> None:
    if not isinstance(sot, dict):
        errors.append(f"{ctx}: sot must be an object")
        return
    kind = sot.get("kind")
    if kind not in _VALID_SOT_KIND:
        errors.append(f"{ctx}: invalid sot kind {kind!r}")
    role = sot.get("role")
    if role not in _VALID_SOT_ROLE:
        errors.append(f"{ctx}: invalid sot role {role!r}")
    ref = sot.get("ref")
    if kind == "url":
        if not isinstance(ref, str) or not ref.strip():
            errors.append(f"{ctx}: url sot ref must be a non-empty string")
    elif kind == "codebase":
        if not isinstance(ref, dict):
            errors.append(f"{ctx}: codebase sot ref must be an object")
        else:
            _require_str(ref, "root", errors, ctx=f"{ctx}.ref")
            strategy = ref.get("strategy")
            if not isinstance(strategy, str) or not strategy.strip():
                errors.append(f"{ctx}.ref: missing or invalid string field 'strategy'")
            elif strategy.strip() not in _VALID_CODEBASE_STRATEGY:
                errors.append(
                    f"{ctx}.ref: invalid codebase strategy {strategy!r} "
                    f"(allowed: {sorted(_VALID_CODEBASE_STRATEGY)})",
                )
    elif ref is not None:
        errors.append(f"{ctx}: sot ref type does not match kind {kind!r}")


def _validate_method(method: Any, errors: list[str], *, ctx: str) -> None:
    if not isinstance(method, dict):
        errors.append(f"{ctx}: method must be an object")
        return
    kind = method.get("kind")
    if kind not in _VALID_METHOD_KIND:
        errors.append(f"{ctx}: invalid method kind {kind!r}")
    source = method.get("source")
    if kind == "external":
        if not isinstance(source, str) or not source.strip():
            errors.append(f"{ctx}: external method source must be a non-empty string")
    elif kind == "builtin":
        if not isinstance(source, dict):
            errors.append(f"{ctx}: builtin method source must be an object")
        else:
            _require_str(source, "procedure_id", errors, ctx=f"{ctx}.source")
    elif source is not None:
        errors.append(f"{ctx}: method source type does not match kind {kind!r}")
    _require_str(method, "focus", errors, ctx=ctx)


def _validate_dimension(dim: Any, errors: list[str], *, ctx: str) -> None:
    if not isinstance(dim, dict):
        errors.append(f"{ctx}: dimension must be an object")
        return
    _require_str(dim, "id", errors, ctx=ctx)
    _require_str(dim, "label", errors, ctx=ctx)
    for target_key in ("eval_target", "remediation_target"):
        target = dim.get(target_key)
        if not isinstance(target, dict):
            errors.append(f"{ctx}: {target_key} must be an object")
        else:
            _require_str(target, "path", errors, ctx=f"{ctx}.{target_key}")
    sots = dim.get("sots")
    if not isinstance(sots, list):
        errors.append(f"{ctx}: sots must be an array")
    else:
        for idx, sot in enumerate(sots):
            _validate_sot(sot, errors, ctx=f"{ctx}.sots[{idx}]")
    _validate_method(dim.get("method"), errors, ctx=f"{ctx}.method")
    review = dim.get("review")
    if not isinstance(review, dict):
        errors.append(f"{ctx}: review must be an object")
    else:
        seq = review.get("seq")
        if not isinstance(seq, int) or seq < 1:
            errors.append(f"{ctx}: review.seq must be a positive integer")
        _require_str(review, "output_path", errors, ctx=f"{ctx}.review")
        _require_str(review, "template", errors, ctx=f"{ctx}.review")


def validate_corpus(data: dict[str, Any]) -> list[str]:
    """Return validation errors; empty list means valid."""
    errors: list[str] = []
    for key in _SCHEMA["required_top_level"]:
        if key not in data:
            errors.append(f"missing required field: '{key}'")
    context = data.get("context")
    if context and context not in _VALID_CONTEXT:
        errors.append(f"invalid context: {context!r}")
    dispatch = data.get("dimension_dispatch")
    if dispatch and dispatch not in _VALID_DISPATCH:
        errors.append(f"invalid dimension_dispatch: {dispatch!r}")
    dimensions = data.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        errors.append("dimensions must be a non-empty array")
    else:
        seen_ids: set[str] = set()
        seen_aliases: set[str] = set()
        seen_seq: set[int] = set()
        for idx, dim in enumerate(dimensions):
            ctx = f"dimensions[{idx}]"
            _validate_dimension(dim, errors, ctx=ctx)
            if isinstance(dim, dict):
                dim_id = dim.get("id", "")
                if dim_id in seen_ids:
                    errors.append(f"duplicate dimension id: {dim_id!r}")
                seen_ids.add(str(dim_id))
                alias = dim.get("legacy_alias")
                if alias:
                    if alias in seen_aliases:
                        errors.append(f"duplicate legacy_alias: {alias!r}")
                    seen_aliases.add(str(alias))
                review = dim.get("review")
                if isinstance(review, dict):
                    seq = review.get("seq")
                    if isinstance(seq, int):
                        if seq in seen_seq:
                            errors.append(f"duplicate review.seq: {seq}")
                        seen_seq.add(seq)
    return errors


def _substitute_string(value: str, bind: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in bind:
            raise ValueError(f"unbound placeholder: {{{key}}}")
        return bind[key]

    return _PLACEHOLDER_RE.sub(repl, value)


def _expand_value(value: Any, bind: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _substitute_string(value, bind)
    if isinstance(value, list):
        return [_expand_value(item, bind) for item in value]
    if isinstance(value, dict):
        return {key: _expand_value(item, bind) for key, item in value.items()}
    return value


def expand_corpus(data: dict[str, Any], bind: dict[str, str]) -> dict[str, Any]:
    """Return a copy of corpus with bind placeholders substituted."""
    errors = validate_corpus(data)
    if errors:
        raise ValueError(f"corpus invalid: {'; '.join(errors)}")
    return _expand_value(copy.deepcopy(data), bind)


def corpus_ref(data: dict[str, Any]) -> str:
    """Return id@version reference string."""
    return f"{data['id']}@{data['version']}"


def dispatch_ids(data: dict[str, Any]) -> list[str]:
    """Return ordered dimension ids for dispatch."""
    errors = validate_corpus(data)
    if errors:
        raise ValueError(f"corpus invalid: {'; '.join(errors)}")
    return [str(dim["id"]) for dim in data["dimensions"]]


def resolve_dim_id(data: dict[str, Any], dim: str) -> str:
    """Map legacy alias (e1/e2/e3) or id to canonical dimension id."""
    for item in data.get("dimensions", []):
        if item.get("id") == dim or item.get("legacy_alias") == dim:
            return str(item["id"])
    raise ValueError(f"unknown dimension: {dim!r}")


def default_corpus_dir() -> Path:
    """Return workflow corpus template directory (tech-plan/corpora)."""
    return Path(__file__).resolve().parents[2] / "tech-plan" / "corpora"


def load_corpus_by_ref(
    ref: str,
    *,
    corpus_dir: Path | None = None,
) -> dict[str, Any]:
    """Load corpus by id@version reference."""
    if "@" not in ref:
        raise ValueError(f"invalid corpus_ref: {ref!r} (expected id@version)")
    corpus_id = ref.split("@", 1)[0]
    base = corpus_dir or default_corpus_dir()
    path = base / f"{corpus_id}.json"
    data = load_corpus(path)
    errors = validate_corpus(data)
    if errors:
        raise ValueError(f"corpus invalid ({path}): {'; '.join(errors)}")
    if corpus_ref(data) != ref:
        raise ValueError(
            f"corpus_ref mismatch: {ref!r} vs {corpus_ref(data)!r}",
        )
    return data


def dispatch_legacy_aliases(data: dict[str, Any]) -> list[str]:
    """Return ordered legacy dispatch keys (e1/e2/e3 or dimension id)."""
    errors = validate_corpus(data)
    if errors:
        raise ValueError(f"corpus invalid: {'; '.join(errors)}")
    return [
        str(dim.get("legacy_alias") or dim["id"])
        for dim in data["dimensions"]
    ]


def _cli() -> int:
    parser = argparse.ArgumentParser(description="EvalCorpus schema I/O")
    parser.add_argument("--schema", action="store_true", help="Print schema JSON")
    parser.add_argument("--validate", action="store_true", help="Validate corpus file")
    parser.add_argument("--expand", action="store_true", help="Expand bind placeholders")
    parser.add_argument("--path", type=Path, help="Path to corpus JSON")
    parser.add_argument(
        "--bind",
        type=Path,
        help="JSON object of bind vars for --expand",
    )
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), ensure_ascii=False, indent=2))
        return 0

    if not args.path:
        print("--validate/--expand requires --path", file=sys.stderr)
        return 1

    path = args.path.resolve()
    try:
        data = load_corpus(path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.validate:
        errors = validate_corpus(data)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "corpus_ref": corpus_ref(data)}, ensure_ascii=False))
        return 0

    if args.expand:
        if not args.bind:
            print("--expand requires --bind", file=sys.stderr)
            return 1
        bind = json.loads(args.bind.read_text(encoding="utf-8"))
        if not isinstance(bind, dict):
            print("--bind must be a JSON object", file=sys.stderr)
            return 1
        bind_str = {str(k): str(v) for k, v in bind.items()}
        try:
            expanded = expand_corpus(data, bind_str)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(expanded, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())

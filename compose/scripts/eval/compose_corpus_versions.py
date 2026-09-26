#!/usr/bin/env python3
"""Compose-owned reusable EvalCorpus identity versions."""

from __future__ import annotations

import json
from pathlib import Path

_VERSIONS_PATH = (
    Path(__file__).resolve().parents[2] / "eval" / "corpus-versions.json"
)


def load_compose_corpus_versions() -> dict[str, str]:
    data = json.loads(_VERSIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError("compose/eval/corpus-versions.json must be a non-empty object")
    versions: dict[str, str] = {}
    for workflow_id, version in data.items():
        key = str(workflow_id).strip()
        value = str(version).strip()
        if not key or not value:
            raise ValueError("corpus version map keys and values must be non-empty")
        versions[key] = value
    return versions


def compose_corpus_id(workflow_id: str) -> str:
    key = str(workflow_id).strip()
    if not key:
        raise ValueError("workflow_id is required")
    return f"{key}-composed"


def compose_corpus_version(workflow_id: str) -> str:
    key = str(workflow_id).strip()
    versions = load_compose_corpus_versions()
    version = versions.get(key, "")
    if not version:
        raise ValueError(f"corpus version map missing workflow {key!r}")
    return version


def compose_corpus_ref(workflow_id: str) -> str:
    return f"{compose_corpus_id(workflow_id)}@{compose_corpus_version(workflow_id)}"

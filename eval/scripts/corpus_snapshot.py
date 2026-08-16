#!/usr/bin/env python3
"""Materialize and verify a per-round EvalCorpus snapshot."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from corpus_schema import normalize_corpus

SNAPSHOT_DIRNAME = "corpus-snapshot"
SNAPSHOT_MANIFEST_NAME = "manifest.json"
SNAPSHOT_CORPUS_NAME = "corpus.json"
SNAPSHOT_REF = f"{SNAPSHOT_DIRNAME}/{SNAPSHOT_MANIFEST_NAME}"
KERNEL_VERSIONS = {
    "eval_corpus_schema": "6",
    "evaluate_state_schema": "8",
    "review_schema": "3",
    "issue_taxonomy": "2",
}
_RUNTIME_DIR_NAMES = frozenset({
    ".git",
    ".eval-admission",
    "corpus-snapshot",
    "eval-admission.json",
})
_RUNTIME_FILE_NAMES = frozenset({
    "evaluate-state.md",
    "eval-admission.json",
    "operation-records.json",
    "_human-resolution-txn.json",
})


def canonical_json_bytes(value: Any) -> bytes:
    """UTF-8 JSON with sorted object keys and no semantic whitespace."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def corpus_digest_from_manifest(manifest: dict[str, Any]) -> str:
    """SHA256 of canonical(manifest without corpus_digest)."""
    payload = {key: value for key, value in manifest.items() if key != "corpus_digest"}
    return sha256_bytes(canonical_json_bytes(payload))


def snapshot_dir(evaluate_dir: Path) -> Path:
    return Path(evaluate_dir) / SNAPSHOT_DIRNAME


def _is_runtime_excluded(relative: str) -> bool:
    parts = Path(relative).parts
    if not parts:
        return True
    if parts[0] in _RUNTIME_DIR_NAMES or parts[-1] in _RUNTIME_FILE_NAMES:
        return True
    if any(part in _RUNTIME_DIR_NAMES for part in parts):
        return True
    if parts[-1].startswith("evaluate") and parts[-1][8:].isdigit():
        return True
    return False


def _validate_snapshot_relative(relative: str) -> str:
    text = str(relative).strip()
    if not text or text.startswith("/") or text.startswith("\\"):
        raise ValueError(f"illegal snapshot path: {relative!r}")
    parts = Path(text).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"illegal snapshot path: {relative!r}")
    return Path(*parts).as_posix()


def _has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor) if path.anchor else Path(path.parts[0])
    if path.is_absolute():
        current = Path(path.anchor)
        rest = path.parts[1:]
    else:
        current = Path(path.parts[0])
        rest = path.parts[1:]
    if current.is_symlink():
        return True
    for part in rest:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _contained_in_roots(resolved: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return True
    return False


def _resolve_under_roots(
    ref: str,
    roots: list[Path],
    *,
    contain_under: Path | None = None,
) -> Path:
    raw = str(ref).strip()
    if not raw:
        raise ValueError("empty source ref")
    candidate = Path(raw)
    if candidate.is_absolute():
        if _has_symlink_component(candidate):
            raise ValueError(f"source ref has symlink component: {raw}")
        resolved = candidate.resolve()
        if not resolved.exists():
            raise ValueError(f"source ref not found: {raw}")
        if not _contained_in_roots(resolved, roots):
            raise ValueError(f"source ref outside allowed roots: {raw}")
        _reject_outside_containment(resolved, contain_under, raw)
        return resolved
    for root in roots:
        trial = (root / raw).resolve()
        try:
            trial.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"source ref escapes root {root}: {raw}") from exc
        if trial.exists():
            if _has_symlink_component(root / raw):
                raise ValueError(f"source ref has symlink component: {raw}")
            _reject_outside_containment(trial, contain_under, raw)
            return trial
    raise ValueError(f"source ref not found: {raw}")


def _reject_outside_containment(
    resolved: Path,
    contain_under: Path | None,
    raw: str,
) -> None:
    if contain_under is None:
        return
    try:
        resolved.relative_to(Path(contain_under).resolve())
    except ValueError as exc:
        raise ValueError(f"source ref outside workflow root: {raw}") from exc


def _write_regular_file(dest: Path, payload: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(dest, flags | nofollow, 0o644)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)


def _read_regular_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"source must be a regular file: {path}")
    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags | nofollow)
    try:
        return os.read(fd, os.path.getsize(path))
    finally:
        os.close(fd)


def _git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _git_worktree_root(path: Path) -> Path:
    top = _git_output(path, "rev-parse", "--show-toplevel").strip()
    if not top:
        raise ValueError("directory SoT requires a git worktree")
    return Path(top)


def _git_nul_paths(root: Path, *args: str) -> list[str]:
    return [item for item in _git_output(root, *args).split("\0") if item]


def _git_stage_mode(worktree: Path, relative: str) -> str:
    listed = _git_output(worktree, "ls-files", "--stage", "-z", "--", relative)
    first = listed.split("\0", 1)[0].strip()
    if not first:
        return ""
    return first.split(" ", 1)[0]


def _directory_file_records(source: Path) -> tuple[str, list[dict[str, Any]]]:
    worktree = _git_worktree_root(source)
    head = _git_output(worktree, "rev-parse", "HEAD").strip()
    current = _git_nul_paths(
        worktree,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    )
    deleted = _git_nul_paths(worktree, "ls-files", "-z", "--deleted")
    head_files = _git_nul_paths(worktree, "ls-tree", "-r", "--name-only", "-z", "HEAD")
    candidates: list[str] = []
    seen_paths: set[str] = set()
    for raw in (*current, *deleted, *head_files):
        if raw in seen_paths:
            continue
        seen_paths.add(raw)
        candidates.append(raw)
    records: list[dict[str, Any]] = []
    seen_fold: dict[str, str] = {}
    worktree_resolved = worktree.resolve()
    source_resolved = source.resolve()
    try:
        source_prefix = source_resolved.relative_to(worktree_resolved).as_posix()
    except ValueError as exc:
        raise ValueError("directory SoT source is outside the git worktree") from exc

    def _listed_under_source(relative: str) -> bool:
        if source_prefix in {".", ""}:
            return True
        return relative == source_prefix or relative.startswith(source_prefix + "/")

    for relative in candidates:
        if not _listed_under_source(relative):
            continue
        abs_path = worktree / relative
        if abs_path.is_symlink():
            raise ValueError(f"directory SoT rejects symlink: {relative}")
        try:
            rel_to_source = abs_path.resolve().relative_to(source_resolved).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"directory SoT path escapes source: {relative}"
            ) from exc
        if rel_to_source == "." or _is_runtime_excluded(rel_to_source):
            continue
        _validate_snapshot_relative(rel_to_source)
        fold = rel_to_source.casefold()
        if fold in seen_fold and seen_fold[fold] != rel_to_source:
            raise ValueError(
                f"case-fold collision: {seen_fold[fold]!r} vs {rel_to_source!r}",
            )
        seen_fold[fold] = rel_to_source
        if _git_stage_mode(worktree, relative) == "160000":
            raise ValueError(f"directory SoT rejects submodule: {rel_to_source}")
        if abs_path.is_symlink():
            raise ValueError(f"directory SoT rejects symlink: {rel_to_source}")
        if not abs_path.exists():
            records.append(
                {
                    "path": rel_to_source,
                    "mode": 0,
                    "digest": "",
                    "status": "deleted",
                    "bytes": b"",
                },
            )
            continue
        mode = abs_path.stat().st_mode
        if stat.S_ISDIR(mode):
            if (abs_path / ".git").exists():
                raise ValueError(f"directory SoT rejects submodule: {rel_to_source}")
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"directory SoT rejects special file: {rel_to_source}")
        payload = _read_regular_file(abs_path)
        records.append(
            {
                "path": rel_to_source,
                "mode": stat.S_IMODE(mode),
                "digest": sha256_bytes(payload),
                "status": "present",
                "bytes": payload,
            },
        )
    records.sort(key=lambda item: item["path"])
    return head, records


def _directory_digest(records: list[dict[str, Any]]) -> str:
    payload = [
        {
            "path": item["path"],
            "mode": item["mode"],
            "digest": item["digest"],
            "status": item.get("status") or "present",
        }
        for item in records
    ]
    return sha256_bytes(canonical_json_bytes(payload))


class _SnapshotBuilder:
    def __init__(self, dest: Path) -> None:
        self.dest = dest
        self.file_seq = 0
        self.dir_seq = 0
        self.assets: list[dict[str, Any]] = []

    def _next_file_name(self) -> str:
        self.file_seq += 1
        return f"f-{self.file_seq:06d}"

    def _next_dir_name(self) -> str:
        self.dir_seq += 1
        return f"d-{self.dir_seq:06d}"

    def add_file(
        self,
        *,
        source_ref: str,
        source_path: Path,
        role: str,
        dimension_id: str,
    ) -> str:
        payload = _read_regular_file(source_path)
        name = self._next_file_name()
        relative = f"assets/files/{name}"
        _validate_snapshot_relative(relative)
        dest = self.dest / relative
        if dest.exists():
            raise ValueError(f"snapshot destination exists: {relative}")
        _write_regular_file(dest, payload)
        digest = sha256_bytes(payload)
        self.assets.append(
            {
                "role": role,
                "dimension_id": dimension_id,
                "kind": "file",
                "source_ref": source_ref,
                "snapshot_path": relative,
                "digest": digest,
            },
        )
        return relative

    def add_directory(
        self,
        *,
        source_ref: str,
        source_path: Path,
        role: str,
        dimension_id: str,
    ) -> str:
        if source_path.is_symlink() or not source_path.is_dir():
            raise ValueError(f"directory SoT must be a directory: {source_ref}")
        head, records = _directory_file_records(source_path)
        name = self._next_dir_name()
        relative = f"assets/directories/{name}"
        view_relative = f"{relative}/view"
        _validate_snapshot_relative(view_relative)
        dest_root = self.dest / relative
        if dest_root.exists():
            raise ValueError(f"snapshot destination exists: {relative}")
        dest_root.mkdir(parents=True, exist_ok=False)
        for item in records:
            if item.get("status") == "deleted":
                continue
            dest = self.dest / view_relative / item["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                raise ValueError(f"snapshot destination exists: {item['path']}")
            _write_regular_file(dest, item["bytes"])
        dir_manifest = {
            "kind": "directory-tree",
            "source_ref": source_ref,
            "git_head": head,
            "overlay": "tracked+untracked-non-ignored",
            "files": [
                {
                    "path": item["path"],
                    "mode": item["mode"],
                    "digest": item["digest"],
                    "status": item.get("status") or "present",
                }
                for item in records
            ],
            "digest": _directory_digest(records),
        }
        (dest_root / "manifest.json").write_bytes(canonical_json_bytes(dir_manifest))
        self.assets.append(
            {
                "role": role,
                "dimension_id": dimension_id,
                "kind": "directory-tree",
                "source_ref": source_ref,
                "snapshot_path": view_relative,
                "digest": dir_manifest["digest"],
                "git_head": head,
            },
        )
        return view_relative


def materialize_corpus_snapshot(
    dest: Path,
    corpus: dict[str, Any],
    *,
    method_roots: list[Path],
    sot_roots: list[Path],
    method_must_stay_under: Path | None = None,
) -> dict[str, Any]:
    """Write a snapshot directory and return the completed manifest."""
    dest = Path(dest)
    if dest.exists():
        raise ValueError(f"snapshot destination already exists: {dest}")
    dest.mkdir(parents=True, exist_ok=False)
    normalized = normalize_corpus(corpus)
    rewritten = json.loads(json.dumps(normalized))
    builder = _SnapshotBuilder(dest)
    for dimension in rewritten["dimensions"]:
        dim_id = str(dimension["id"])
        method = dimension["method"]
        method_ref = str(method.get("ref") or "")
        method["ref"] = builder.add_file(
            source_ref=method_ref,
            source_path=_resolve_under_roots(
                method_ref,
                method_roots,
                contain_under=method_must_stay_under,
            ),
            role="method",
            dimension_id=dim_id,
        )
        template_ref = str(dimension.get("review", {}).get("template") or "")
        if template_ref:
            dimension["review"]["template"] = builder.add_file(
                source_ref=template_ref,
                source_path=_resolve_under_roots(
                    template_ref,
                    method_roots,
                    contain_under=method_must_stay_under,
                ),
                role="review-template",
                dimension_id=dim_id,
            )
        for sot in dimension.get("sots") or []:
            sot_ref = str(sot.get("ref") or "")
            if not sot_ref:
                raise ValueError(f"empty SoT ref on dimension {dim_id}")
            source = _resolve_under_roots(sot_ref, sot_roots)
            if source.is_dir() or sot_ref == ".":
                sot["ref"] = builder.add_directory(
                    source_ref=sot_ref,
                    source_path=source,
                    role="sot",
                    dimension_id=dim_id,
                )
            else:
                sot["ref"] = builder.add_file(
                    source_ref=sot_ref,
                    source_path=source,
                    role="sot",
                    dimension_id=dim_id,
                )
    corpus_bytes = canonical_json_bytes(rewritten)
    (dest / SNAPSHOT_CORPUS_NAME).write_bytes(corpus_bytes)
    manifest: dict[str, Any] = {
        "version": 1,
        "corpus_ref": f"{rewritten['id']}@{rewritten['version']}",
        "kernel_versions": dict(KERNEL_VERSIONS),
        "corpus_path": SNAPSHOT_CORPUS_NAME,
        "corpus_sha256": sha256_bytes(corpus_bytes),
        "assets": builder.assets,
    }
    manifest["corpus_digest"] = corpus_digest_from_manifest(manifest)
    (dest / SNAPSHOT_MANIFEST_NAME).write_bytes(canonical_json_bytes(manifest))
    return manifest


def load_materialized_corpus(
    snapshot_root: Path,
    *,
    expected_digest: str,
) -> dict[str, Any]:
    """Verify snapshot integrity and return a runtime corpus with absolute refs."""
    root = Path(snapshot_root)
    manifest_path = root / SNAPSHOT_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError(
            f"incompatible_round: corpus snapshot missing {SNAPSHOT_MANIFEST_NAME}",
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("incompatible_round: corpus snapshot manifest is not JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("incompatible_round: corpus snapshot manifest must be an object")
    actual = corpus_digest_from_manifest(manifest)
    if actual != str(manifest.get("corpus_digest") or ""):
        raise ValueError("incompatible_round: corpus snapshot manifest digest drifted")
    if actual != expected_digest:
        raise ValueError("incompatible_round: corpus snapshot digest mismatch")
    corpus_path = root / str(manifest.get("corpus_path") or SNAPSHOT_CORPUS_NAME)
    corpus_bytes = corpus_path.read_bytes()
    if sha256_bytes(corpus_bytes) != str(manifest.get("corpus_sha256") or ""):
        raise ValueError("incompatible_round: corpus.json digest drifted")
    for asset in manifest.get("assets") or []:
        relative = _validate_snapshot_relative(str(asset.get("snapshot_path") or ""))
        asset_path = root / relative
        if str(asset.get("kind")) == "directory-tree":
            dir_manifest_path = asset_path.parent / "manifest.json"
            if not dir_manifest_path.is_file():
                raise ValueError(
                    f"incompatible_round: directory snapshot missing {relative}",
                )
            dir_manifest = json.loads(dir_manifest_path.read_text(encoding="utf-8"))
            records = []
            expected_present: set[str] = set()
            for item in dir_manifest.get("files") or []:
                rel = _validate_snapshot_relative(str(item.get("path") or ""))
                file_path = asset_path / rel
                if str(item.get("status") or "present") == "deleted":
                    if file_path.exists():
                        raise ValueError(
                            f"incompatible_round: deleted snapshot path still present {rel}",
                        )
                    records.append(item)
                    continue
                payload = _read_regular_file(file_path)
                if sha256_bytes(payload) != str(item.get("digest") or ""):
                    raise ValueError(
                        f"incompatible_round: directory asset drifted {item['path']}",
                    )
                expected_present.add(rel)
                records.append(item)
            if asset_path.is_dir():
                for found in asset_path.rglob("*"):
                    if found.is_dir():
                        continue
                    extra = found.relative_to(asset_path).as_posix()
                    if extra not in expected_present:
                        raise ValueError(
                            f"incompatible_round: unexpected snapshot file {extra}",
                        )
            if _directory_digest(
                [
                    {
                        "path": item["path"],
                        "mode": item["mode"],
                        "digest": item["digest"],
                        "status": item.get("status") or "present",
                    }
                    for item in records
                ],
            ) != str(asset.get("digest") or ""):
                raise ValueError("incompatible_round: directory snapshot digest drifted")
            continue
        payload = _read_regular_file(asset_path)
        if sha256_bytes(payload) != str(asset.get("digest") or ""):
            raise ValueError(f"incompatible_round: snapshot asset drifted {relative}")
    corpus = json.loads(corpus_bytes.decode("utf-8"))
    return _absolutize_snapshot_refs(corpus, root)


def _absolutize_snapshot_refs(corpus: dict[str, Any], root: Path) -> dict[str, Any]:
    rewritten = json.loads(json.dumps(corpus))
    for dimension in rewritten.get("dimensions") or []:
        method = dimension.get("method") or {}
        if method.get("ref"):
            method["ref"] = (root / str(method["ref"])).resolve().as_posix()
        review = dimension.get("review") or {}
        if review.get("template"):
            review["template"] = (root / str(review["template"])).resolve().as_posix()
        for sot in dimension.get("sots") or []:
            if sot.get("ref"):
                sot["ref"] = (root / str(sot["ref"])).resolve().as_posix()
    return rewritten


def publish_snapshot_dir(staging_snapshot: Path, evaluate_dir: Path) -> Path:
    """Atomically publish a staged snapshot into evaluate_dir/corpus-snapshot."""
    dest = snapshot_dir(evaluate_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise ValueError(f"published snapshot already exists: {dest}")
    os.replace(staging_snapshot, dest)
    return dest

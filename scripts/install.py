#!/usr/bin/env python3
"""Install lulu-dev-workflow runtime into the platform skill directory.

  python3 install.py --platform cursor [--from-dir PATH | --repo REPO --ref REF]
  python3 install.py --platform copilot [--from-dir PATH | --repo REPO --ref REF]

Installs to:
  cursor  -> ~/.cursor/skills/lulu-dev-workflow/
  copilot -> ~/.copilot/skills/lulu-dev-workflow/
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

DEFAULT_REPO = "lulufoo/lulu-dev-skills"
DEFAULT_REF  = "main"
BASE         = "lulu-dev-workflow"

# Root-level scripts (relative to BASE/scripts/)
ROOT_SCRIPTS = (
    "archive_common.py",
    "feature_init.py",
    "hook_guard.py",
    "init.py",
    "install.py",
    "prune_features.py",
)
ROOT_PLATFORMS = (
    "platforms/__init__.py",
    "platforms/cursor.py",
    "platforms/copilot.py",
)

# Stage definitions: name -> list of scripts present in that stage
STAGE_SCRIPTS: dict = {
    "code":       ["archive.py", "hook_guard.py", "init.py", "start.py", "workflow_common.py"],
    "work-order": ["archive.py", "hook_guard.py", "init.py", "start.py", "workflow_common.py"],
    "tech":       ["archive.py", "hook_guard.py", "init.py", "start.py", "workflow_common.py"],
    "product":    ["archive.py", "hook_guard.py", "init.py", "start.py", "workflow_common.py"],
    "diagnostic": ["archive.py", "hook_guard.py", "start.py", "workflow_common.py"],
}
# Stages that have transition-whitelist.json
STAGE_WHITELIST = {"code", "work-order", "tech", "product"}
# product has templates/
PRODUCT_TEMPLATES = (
    "delivery-approval.template.json",
    "state.template.json",
    "workflow-config.template.json",
)


def _skill_dst(platform: str) -> Path:
    if platform == "copilot":
        return Path.home() / ".copilot" / "skills" / "lulu-dev-workflow"
    return Path.home() / ".cursor" / "skills" / "lulu-dev-workflow"


def _gh_api_content(owner: str, repo: str, ref: str, path: str) -> bytes:
    result = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/contents/{path}?ref={ref}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"gh api failed for {path}: {err}\nHint: run `gh auth login`.")
    detail = json.loads(result.stdout)
    content_b64 = detail.get("content") or ""
    if detail.get("encoding") == "base64":
        return base64.b64decode(content_b64.replace("\n", ""))
    return content_b64.encode("utf-8")


def _chmod_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _write(dst: Path, data: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)


# ── local install ──────────────────────────────────────────────────────────────

def _install_from_local(src: Path, dst: Path) -> None:
    src = src.resolve()
    if not (src / "SKILL.md").is_file():
        raise FileNotFoundError(f"SKILL.md not found under {src}")

    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "SKILL.md", dst / "SKILL.md")

    # Root scripts
    scripts_dst = dst / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    (scripts_dst / "platforms").mkdir(parents=True, exist_ok=True)
    scripts_src = src / "scripts"
    for name in ROOT_SCRIPTS:
        f = scripts_src / name
        if not f.is_file():
            raise FileNotFoundError(f"Missing: {f}")
        dest = scripts_dst / name
        shutil.copy2(f, dest)
        _chmod_executable(dest)
    for rel in ROOT_PLATFORMS:
        f = scripts_src / rel
        if not f.is_file():
            raise FileNotFoundError(f"Missing: {f}")
        dest = scripts_dst / rel
        shutil.copy2(f, dest)
        _chmod_executable(dest)

    # Stages
    for stage, scripts in STAGE_SCRIPTS.items():
        stage_src = src / stage
        stage_dst = dst / stage
        stage_scripts_dst = stage_dst / "scripts"
        stage_scripts_dst.mkdir(parents=True, exist_ok=True)
        if (stage_src / "SKILL.md").is_file():
            shutil.copy2(stage_src / "SKILL.md", stage_dst / "SKILL.md")
        if stage in STAGE_WHITELIST:
            wl = stage_src / "transition-whitelist.json"
            if not wl.is_file():
                raise FileNotFoundError(f"Missing: {wl}")
            shutil.copy2(wl, stage_dst / "transition-whitelist.json")
        for name in scripts:
            f = stage_src / "scripts" / name
            if not f.is_file():
                raise FileNotFoundError(f"Missing: {f}")
            dest = stage_scripts_dst / name
            shutil.copy2(f, dest)
            _chmod_executable(dest)
        if stage == "product":
            templates_dst = stage_dst / "templates"
            templates_dst.mkdir(parents=True, exist_ok=True)
            for tpl in PRODUCT_TEMPLATES:
                f = stage_src / "templates" / tpl
                if not f.is_file():
                    raise FileNotFoundError(f"Missing: {f}")
                shutil.copy2(f, templates_dst / tpl)


# ── GitHub install ─────────────────────────────────────────────────────────────

def _install_from_github(repo: str, ref: str, dst: Path) -> None:
    owner, repo_name = repo.split("/", 1)
    dst.mkdir(parents=True, exist_ok=True)

    _write(dst / "SKILL.md",
           _gh_api_content(owner, repo_name, ref, f"{BASE}/SKILL.md"))

    # Root scripts
    scripts_dst = dst / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    (scripts_dst / "platforms").mkdir(parents=True, exist_ok=True)
    for name in ROOT_SCRIPTS:
        dest = scripts_dst / name
        dest.write_bytes(_gh_api_content(owner, repo_name, ref, f"{BASE}/scripts/{name}"))
        _chmod_executable(dest)
    for rel in ROOT_PLATFORMS:
        dest = scripts_dst / rel
        dest.write_bytes(_gh_api_content(owner, repo_name, ref, f"{BASE}/scripts/{rel}"))
        _chmod_executable(dest)

    # Stages
    for stage, scripts in STAGE_SCRIPTS.items():
        stage_dst = dst / stage
        stage_scripts_dst = stage_dst / "scripts"
        stage_scripts_dst.mkdir(parents=True, exist_ok=True)
        _write(stage_dst / "SKILL.md",
               _gh_api_content(owner, repo_name, ref, f"{BASE}/{stage}/SKILL.md"))
        if stage in STAGE_WHITELIST:
            _write(stage_dst / "transition-whitelist.json",
                   _gh_api_content(owner, repo_name, ref,
                                   f"{BASE}/{stage}/transition-whitelist.json"))
        for name in scripts:
            dest = stage_scripts_dst / name
            dest.write_bytes(
                _gh_api_content(owner, repo_name, ref, f"{BASE}/{stage}/scripts/{name}")
            )
            _chmod_executable(dest)
        if stage == "product":
            templates_dst = stage_dst / "templates"
            templates_dst.mkdir(parents=True, exist_ok=True)
            for tpl in PRODUCT_TEMPLATES:
                _write(templates_dst / tpl,
                       _gh_api_content(owner, repo_name, ref,
                                       f"{BASE}/product/templates/{tpl}"))


# ── cleanup ────────────────────────────────────────────────────────────────────

def _cleanup_dst(dst: Path) -> None:
    shutil.rmtree(dst / "tests", ignore_errors=True)
    shutil.rmtree(dst / ".pytest_cache", ignore_errors=True)
    for stage in STAGE_SCRIPTS:
        shutil.rmtree(dst / stage / "tests", ignore_errors=True)
        shutil.rmtree(dst / stage / ".pytest_cache", ignore_errors=True)


# ── public API ─────────────────────────────────────────────────────────────────

def install(
    platform: str,
    *,
    from_dir: Optional[str] = None,
    repo: str = DEFAULT_REPO,
    ref: str = DEFAULT_REF,
) -> Path:
    dst = _skill_dst(platform)
    if from_dir:
        _install_from_local(Path(from_dir), dst)
    else:
        _install_from_github(repo, ref, dst)
    _cleanup_dst(dst)
    return dst


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install lulu-dev-workflow into platform skill directory"
    )
    parser.add_argument(
        "--platform", default="cursor", choices=["cursor", "copilot"],
        help="Target platform (cursor or copilot)",
    )
    parser.add_argument(
        "--from-dir", dest="from_dir", default=None,
        help="Install from local clone path (the lulu-dev-workflow directory)",
    )
    parser.add_argument(
        "--repo", default=os.environ.get("REPO", DEFAULT_REPO),
        help=f"GitHub repo (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--ref", default=os.environ.get("REF", DEFAULT_REF),
        help=f"Git ref (default: {DEFAULT_REF})",
    )
    args = parser.parse_args(argv)

    try:
        dst = install(args.platform, from_dir=args.from_dir, repo=args.repo, ref=args.ref)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        print(f"[install] {exc}", file=sys.stderr)
        return 1

    n_root = len(ROOT_SCRIPTS) + len(ROOT_PLATFORMS)
    n_stages = sum(len(v) for v in STAGE_SCRIPTS.values())
    print(f"[install] Installed lulu-dev-workflow ({args.platform}) to {dst.as_posix()}")
    print(f"  SKILL.md + scripts/ ({n_root} root py files)")
    print(f"  {len(STAGE_SCRIPTS)} stages ({n_stages} stage py files)")
    print("  Excluded: tests/, .pytest_cache/ (dev-only; run pytest in repo clone)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

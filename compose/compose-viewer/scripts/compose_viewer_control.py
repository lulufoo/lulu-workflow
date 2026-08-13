#!/usr/bin/env python3
"""Compose Viewer mount control (archive-25.0 unified arc).

Subcommands: mount · status · stop

- Syncs ``compose-viewer/assets/compose-viewer.html`` into the active slice.
- Writes ``_compose-viewer.json`` with caller ``arc_source``.
- Requires on-disk unified ``narrative-arc`` with ``status=write_ready``.
- Does not edit Viewer HTML; basename Formal ban removed at mount control.
- Serves on ``127.0.0.1:8390``.
- ``mount`` success stdout is **URL only** (one line); errors on stderr.
- Mount conflict: reuse same root, else stop-old-then-start.

CLI: ``python3 compose_viewer_control.py --help``

Process how: docs/domain/archive/compose/archive-25.0/
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_RUNNER_SCRIPTS = Path(__file__).resolve().parent
_VIEWER_ROOT = _RUNNER_SCRIPTS.parent
_COMPOSE = _VIEWER_ROOT.parent
_SCRIPTS = _COMPOSE / "scripts"
_NARRATIVE_SCRIPTS = _COMPOSE / "narrative-arc-runner" / "scripts"
for _p in (_SCRIPTS, _NARRATIVE_SCRIPTS, _RUNNER_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from l_ledger_schema import active_slice_dir  # noqa: E402
from narrative_arc_schema import (  # noqa: E402
    DEFAULT_DISPLAY_ARC_BASENAME,
    is_write_ready,
    load_narrative_arc,
)

DEFAULT_PORT = 8390
VIEWER_NAME = "compose-viewer.html"
ASSET = _VIEWER_ROOT / "assets" / VIEWER_NAME
STATE_NAME = "_compose-viewer.server.json"
CONFIG_NAME = "_compose-viewer.json"
LOG_NAME = "_compose-viewer.server.log"


def _slice(revision_dir: str) -> Path:
    return active_slice_dir(Path(revision_dir).resolve())


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _state_path(slice_dir: Path) -> Path:
    return slice_dir / STATE_NAME


def _config_path(slice_dir: Path) -> Path:
    return slice_dir / CONFIG_NAME


def _sync_asset(slice_dir: Path) -> Path:
    if not ASSET.is_file():
        raise ValueError(f"viewer asset missing: {ASSET}")
    dest = slice_dir / VIEWER_NAME
    shutil.copy2(ASSET, dest)
    return dest


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _load_state(slice_dir: Path) -> dict[str, Any] | None:
    path = _state_path(slice_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _write_config(slice_dir: Path, arc_file: str) -> Path:
    if Path(arc_file).is_absolute():
        raise ValueError("arc-file must be a basename relative to slice dir")
    rel = Path(arc_file).name
    arc_path = slice_dir / rel
    if not arc_path.is_file():
        raise ValueError(f"arc file not found: {arc_path}")
    try:
        data = load_narrative_arc(arc_path)
    except ValueError as exc:
        raise ValueError(f"invalid narrative arc for mount: {exc}") from exc
    if not is_write_ready(data):
        raise ValueError("mount requires status=write_ready")
    cfg = {
        "version": "1",
        "arc_source": f"./{rel}",
        "facts_source": "./_facts.json",
    }
    path = _config_path(slice_dir)
    path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _stop_pid(pid: int) -> None:
    if pid and _pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not _pid_alive(pid):
                break
            time.sleep(0.05)


def _listener_pids(port: int) -> list[int]:
    """PIDs listening on TCP port (macOS/Linux ``lsof``). Empty if unavailable."""
    try:
        out = subprocess.check_output(
            ["lsof", "-nP", "-iTCP:%d" % port, "-sTCP:LISTEN", "-t"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    pids: list[int] = []
    for line in out.split():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid not in pids:
            pids.append(pid)
    return pids


def _stop_port_listeners(port: int) -> list[int]:
    """Stop any process listening on ``port`` (cross-root stop-old-then-start)."""
    stopped: list[int] = []
    for pid in _listener_pids(port):
        _stop_pid(pid)
        stopped.append(pid)
    for _ in range(20):
        if not _listener_pids(port):
            break
        time.sleep(0.05)
    return stopped


def _clear_foreign_state(root: Path) -> None:
    path = root / STATE_NAME
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _start_server(slice_dir: Path, port: int) -> int:
    log_path = slice_dir / LOG_NAME
    log_f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(slice_dir),
        stdout=log_f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    time.sleep(0.3)
    if proc.poll() is not None:
        raise RuntimeError(f"failed to start http.server on {port}; see {log_path}")
    state_payload = {
        "pid": proc.pid,
        "port": port,
        "root": str(slice_dir),
        "started_at": time.time(),
    }
    _state_path(slice_dir).write_text(
        json.dumps(state_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return proc.pid


def cmd_mount(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    port = int(args.port or DEFAULT_PORT)
    arc_file = str(args.arc_file or DEFAULT_DISPLAY_ARC_BASENAME).strip()
    try:
        viewer = _sync_asset(slice_dir)
        cfg = _write_config(slice_dir, arc_file)
    except ValueError as exc:
        return _fail(str(exc))

    state = _load_state(slice_dir)
    if state and state.get("port") == port and _pid_alive(int(state.get("pid") or 0)):
        root = Path(str(state.get("root") or ""))
        if root.resolve() == slice_dir.resolve():
            url = f"http://127.0.0.1:{port}/{VIEWER_NAME}?v={int(time.time())}"
            print(url)
            return 0
        _stop_pid(int(state.get("pid") or 0))
        _clear_foreign_state(root)
        _state_path(slice_dir).unlink(missing_ok=True)

    stopped = _stop_port_listeners(port)
    for pid in stopped:
        if state and int(state.get("pid") or 0) == pid:
            _clear_foreign_state(Path(str(state.get("root") or "")))

    try:
        _start_server(slice_dir, port)
    except RuntimeError as exc:
        return _fail(str(exc))

    del viewer, cfg, stopped
    url = f"http://127.0.0.1:{port}/{VIEWER_NAME}?v={int(time.time())}"
    print(url)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    state = _load_state(slice_dir)
    if not state:
        return _ok({"ok": True, "running": False, "root": str(slice_dir)})
    pid = int(state.get("pid") or 0)
    running = _pid_alive(pid)
    port = int(state.get("port") or DEFAULT_PORT)
    url = f"http://127.0.0.1:{port}/{VIEWER_NAME}" if running else ""
    return _ok(
        {
            "ok": True,
            "running": running,
            "pid": pid,
            "port": port,
            "root": state.get("root"),
            "url": url,
        }
    )


def cmd_stop(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    state = _load_state(slice_dir)
    if not state:
        return _ok({"ok": True, "stopped": False, "reason": "no state"})
    pid = int(state.get("pid") or 0)
    _stop_pid(pid)
    _state_path(slice_dir).unlink(missing_ok=True)
    return _ok({"ok": True, "stopped": True, "pid": pid})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("mount")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument(
        "--arc-file",
        default=DEFAULT_DISPLAY_ARC_BASENAME,
        help=(
            f"Basename under slice (default {DEFAULT_DISPLAY_ARC_BASENAME}); "
            "must be write_ready narrative-arc"
        ),
    )
    p.set_defaults(func=cmd_mount)

    p = sub.add_parser("status")
    p.add_argument("--revision-dir", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("stop")
    p.add_argument("--revision-dir", required=True)
    p.set_defaults(func=cmd_stop)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

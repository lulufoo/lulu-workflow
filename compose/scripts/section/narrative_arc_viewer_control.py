#!/usr/bin/env python3
"""Mount local static viewer for narrative-arc draft (archive-9.0 T5).

Subcommands: mount · status · stop

- Syncs skill asset ``compose/assets/narrative-arc-viewer.html`` into the
  active slice directory.
- Serves that directory on ``127.0.0.1:8390``.
- Prints URL only (does not open a browser).

CLI: ``python3 narrative_arc_viewer_control.py --help``

Process how: docs/domain/archive/compose/archive-9.0/
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

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
_COMPOSE = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from discussion_pointer_schema import active_slice_dir  # noqa: E402

DEFAULT_PORT = 8390
VIEWER_NAME = "narrative-arc-viewer.html"
ASSET = _COMPOSE / "assets" / VIEWER_NAME
STATE_NAME = "_narrative-arc-viewer.server.json"


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


def cmd_mount(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    port = int(args.port or DEFAULT_PORT)
    try:
        viewer = _sync_asset(slice_dir)
    except ValueError as exc:
        return _fail(str(exc))

    state = _load_state(slice_dir)
    if state and state.get("port") == port and _pid_alive(int(state.get("pid") or 0)):
        root = Path(str(state.get("root") or ""))
        if root.resolve() == slice_dir.resolve():
            url = f"http://127.0.0.1:{port}/{VIEWER_NAME}?v={int(time.time())}"
            return _ok(
                {
                    "ok": True,
                    "reused": True,
                    "url": url,
                    "root": str(slice_dir),
                    "pid": state.get("pid"),
                    "viewer": str(viewer),
                }
            )
        return _fail(
            f"port {port} already serving different root {root}; stop first",
        )

    # Start http.server in background
    log_path = slice_dir / "_narrative-arc-viewer.server.log"
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
        return _fail(f"failed to start http.server on {port}; see {log_path}")
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
    url = f"http://127.0.0.1:{port}/{VIEWER_NAME}?v={int(time.time())}"
    return _ok(
        {
            "ok": True,
            "reused": False,
            "url": url,
            "root": str(slice_dir),
            "pid": proc.pid,
            "viewer": str(viewer),
        }
    )


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
    if pid and _pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
    _state_path(slice_dir).unlink(missing_ok=True)
    return _ok({"ok": True, "stopped": True, "pid": pid})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("mount")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
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

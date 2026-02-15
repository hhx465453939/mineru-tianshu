#!/usr/bin/env python3
"""
One-click local launcher for frontend and backend development services.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def resolve_backend_python() -> str:
    if os.name == "nt":
        venv_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = BACKEND_DIR / ".venv" / "bin" / "python"

    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def start_process(command: list[str], cwd: Path, name: str) -> subprocess.Popen:
    print(f"[start] {name}: {' '.join(command)} (cwd={cwd})")
    return subprocess.Popen(command, cwd=str(cwd))


def terminate_process(name: str, process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    print(f"[stop] {name}")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print(f"[kill] {name}")
        process.kill()
        process.wait()


def main() -> int:
    backend_python = resolve_backend_python()
    backend_output_dir = str(ROOT_DIR / "data" / "output")
    backend_cmd = [backend_python, "start_all.py", "--output-dir", backend_output_dir]

    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev"]

    backend = start_process(backend_cmd, BACKEND_DIR, "backend")
    frontend = start_process(frontend_cmd, FRONTEND_DIR, "frontend")

    processes = [("backend", backend), ("frontend", frontend)]

    def shutdown(*_: object) -> None:
        for name, process in reversed(processes):
            terminate_process(name, process)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("[ready] backend and frontend are running. Press Ctrl+C to stop.")
    try:
        while True:
            for name, process in processes:
                code = process.poll()
                if code is not None:
                    print(f"[exit] {name} exited with code {code}")
                    shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

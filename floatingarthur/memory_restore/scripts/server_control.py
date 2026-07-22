"""Start, stop, and inspect the Flask API on the Linux GPU server."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
PID_FILE = RUNTIME_DIR / "flask.pid"
LOG_FILE = RUNTIME_DIR / "flask.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--port", type=int, default=5050)
    return parser.parse_args()


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def process_is_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def start(port: int) -> None:
    pid = read_pid()
    if process_is_running(pid):
        print(f"Flask is already running (PID {pid}, port {port}).")
        return
    if PID_FILE.exists():
        PID_FILE.unlink()
    if port_is_open(port):
        raise RuntimeError(f"Port {port} is already in use by an unmanaged process.")

    RUNTIME_DIR.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "flask",
                "--app",
                "app:create_app",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    time.sleep(0.5)
    if not process_is_running(process.pid):
        raise RuntimeError(f"Flask did not start. Check {LOG_FILE}.")
    print(f"Flask started (PID {process.pid}, port {port}).")


def stop() -> None:
    pid = read_pid()
    if not process_is_running(pid):
        PID_FILE.unlink(missing_ok=True)
        print("Flask is not running under this controller.")
        return

    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not process_is_running(pid):
            PID_FILE.unlink(missing_ok=True)
            print(f"Flask stopped (PID {pid}).")
            return
        time.sleep(0.25)
    raise RuntimeError(f"Flask PID {pid} did not stop. Check {LOG_FILE}.")


def status(port: int) -> None:
    pid = read_pid()
    if process_is_running(pid):
        print(f"Flask is running (PID {pid}, port {port}, local_port_open={port_is_open(port)}).")
    else:
        print(f"Flask is stopped (local_port_open={port_is_open(port)}).")


def main() -> None:
    args = parse_args()
    if args.action == "start":
        start(args.port)
    elif args.action == "stop":
        stop()
    else:
        status(args.port)


if __name__ == "__main__":
    main()

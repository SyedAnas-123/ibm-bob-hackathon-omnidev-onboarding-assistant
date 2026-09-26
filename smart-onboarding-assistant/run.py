"""
run.py — Launch the Smart Developer Onboarding Assistant
=========================================================
Usage (from the smart-onboarding-assistant directory):

    python run.py

The FastAPI server starts and serves both the API and the enterprise
HTML frontend.  Open the URL printed in the terminal to access the UI.

Optional environment variables:
    API_HOST   Bind host  (default: 127.0.0.1 — use 0.0.0.0 for LAN access)
    API_PORT   Port       (default: 8000)
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import threading
import time

# Force UTF-8 on Windows so emoji / non-ASCII output doesn't crash.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = os.environ.get("API_PORT", "8000")

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stream_output(stream, prefix: str) -> None:
    try:
        for raw in stream:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            print(f"{prefix} {line}", flush=True)
    except ValueError:
        pass  # stream closed


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    python = sys.executable

    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"

    fastapi_cmd = [
        python, "-m", "uvicorn",
        "main:app",
        "--host", API_HOST,
        "--port", API_PORT,
    ]

    print("=" * 62, flush=True)
    print("  Smart Developer Onboarding Assistant", flush=True)
    print("=" * 62, flush=True)
    print(f"  App  (UI)  ->  http://{API_HOST}:{API_PORT}/", flush=True)
    print(f"  API  docs  ->  http://{API_HOST}:{API_PORT}/docs", flush=True)
    print("=" * 62, flush=True)
    print("  Press Ctrl-C to stop.\n", flush=True)

    try:
        api_proc = subprocess.Popen(
            fastapi_cmd,
            cwd=HERE,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        t = threading.Thread(
            target=_stream_output,
            args=(api_proc.stdout, "[API]"),
            daemon=True,
        )
        t.start()

        while True:
            if api_proc.poll() is not None:
                print(
                    f"\n[run.py] Server (pid {api_proc.pid}) exited with "
                    f"code {api_proc.returncode}.",
                    flush=True,
                )
                break
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[run.py] Ctrl-C received — shutting down ...", flush=True)

    finally:
        _terminate(api_proc)
        t.join(timeout=2)
        print("[run.py] Server stopped.", flush=True)


if __name__ == "__main__":
    main()

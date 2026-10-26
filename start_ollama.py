#!/usr/bin/env python3
"""Start local Ollama if appropriate, then run HouseOfBigBeans readiness checks.

Place this file in the MoneyPrinterV2 repository root, next to config.json.
Run: .venv/bin/python start_ollama.py

No installation, model download, paid content generation, upload, scheduling,
configuration change, or repository write is performed. If an already-installed
local server is stopped, it is started bound only to the loopback interface.
Its output goes to a private local temporary log, never into this chat.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

import errno
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.json"


def read_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        raise ValueError("config.json must contain a JSON object.")
    return config

def request_models(base_url, *, timeout=5):
    """Check HTTP status and JSON together; a 404 is not a healthy Ollama server."""
    try:
        with urlopen(base_url.rstrip("/") + "/api/tags", timeout=timeout) as response:
            status = response.status
            if not 200 <= status < 300:
                return None, f"HTTP {status}"
            data = json.load(response)
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            return None, "Invalid model-list response"
        models = [m.get("name") or m.get("model") for m in data["models"] if isinstance(m, dict)]
        return [name for name in models if isinstance(name, str) and name], None
    except HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except URLError as exc:
        # Classify common failures without printing URLs or exception messages.
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError) or getattr(reason, "errno", None) == errno.ECONNREFUSED:
            return None, "Connection refused"
        if isinstance(reason, socket.gaierror):
            return None, "Name resolution failed"
        if isinstance(reason, TimeoutError):
            return None, "Connection timed out"
        return None, "URLError"
    except TimeoutError:
        return None, "Connection timed out"
    except Exception as exc:
        # Exception messages may contain credential-bearing URLs. Print only a type.
        return None, type(exc).__name__


def ensure_ollama(config: dict) -> int:
    """Check the configured endpoint; start only a refused loopback HTTP service.

    Remote servers, occupied ports, authentication errors, and timeouts are not
    repaired by starting another process. No configuration or model is changed.
    """
    base = config.get("ollama_base_url") or "http://127.0.0.1:11434"
    try:
        if not isinstance(base, str) or base != base.strip():
            raise ValueError
        address = urlsplit(base)
        if (address.scheme not in ("http", "https") or not address.hostname
                or address.username is not None or address.password is not None
                or address.query or address.fragment):
            raise ValueError
        port = address.port or (443 if address.scheme == "https" else 80)
        if address.port == 0:
            raise ValueError
    except (TypeError, ValueError):
        print("[FAIL] Check ollama_base_url: use an HTTP(S) base URL without embedded credentials, query, or fragment. Value hidden.")
        return 1

    models, problem = request_models(base, timeout=2)
    if models is not None:
        print("[OK] Configured Ollama server is reachable. No new process started.")
        return 0
    print("[INFO] Configured Ollama check: " + problem)
    is_local = (address.scheme == "http"
                and address.hostname in ("localhost", "127.0.0.1", "::1")
                and address.path in ("", "/"))
    if not is_local:
        print("[FAIL] Endpoint is not a direct loopback HTTP server. No local service or settings changed.")
        return 1
    if problem != "Connection refused":
        print("[FAIL] Not a refused local connection. Check the endpoint, proxy, or existing service; no new process started.")
        return 1

    executable = shutil.which("ollama")
    if executable is None:
        print("[FAIL] Ollama executable not found on PATH. The Python ollama package does not install the server.")
        return 1

    bind_host = "[::1]" if address.hostname == "::1" else "127.0.0.1"
    environment = os.environ.copy()
    environment["OLLAMA_HOST"] = f"{bind_host}:{port}"
    try:
        # A unique file with mode 0600 avoids overwriting logs or exposing
        # environment values that Ollama may include in its own startup output.
        descriptor, log_path = tempfile.mkstemp(prefix="houseofbigbeans-ollama-", suffix=".log")
        with os.fdopen(descriptor, "wb") as log:
            process = subprocess.Popen(
                [executable, "serve"], env=environment,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError:
        print("[FAIL] Could not start Ollama. No software was installed or configuration changed.")
        return 1

    print(f"[INFO] Starting Ollama on loopback port {port}; local startup log: {log_path}")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        models, problem = request_models(base, timeout=1)
        if models is not None:
            print("[OK] Configured Ollama server is reachable. No models downloaded or content generated.")
            return 0
        if process.poll() is not None:
            print("[FAIL] Ollama exited before becoming ready. Inspect the local startup log; redact secrets before sharing it.")
            return 1
        time.sleep(0.5)
    print("[FAIL] Ollama did not become ready within 20 seconds. It was not forcibly stopped; inspect the local startup log.")
    return 1


def main() -> int:
    try:
        config = read_config(ROOT_DIR / "config.json")
    except (OSError, ValueError):
        print("[FAIL] config.json is missing, unreadable, or invalid. No file was changed.")
        return 1
    result = ensure_ollama(config)
    if result:
        return result
    checker = ROOT_DIR / "scripts" / "generate_preview.py"
    if not checker.is_file():
        print("[FAIL] Put start_ollama.py in the MoneyPrinterV2 root folder, next to config.json.")
        return 1
    print("[INFO] Running HouseOfBigBeans readiness checks only.", flush=True)
    return subprocess.run(
        [sys.executable, str(checker), "--account", "HouseOfBigBeans", "--check-only"],
        cwd=ROOT_DIR, check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())

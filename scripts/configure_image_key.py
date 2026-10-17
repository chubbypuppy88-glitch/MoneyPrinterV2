#!/usr/bin/env python3
"""Privately replace a Gemini key, verify model access, optionally run a preview.

No key is accepted as a command-line argument or printed. Only the ignored local
config.json is updated, after a successful Google model-metadata request. That
request does not generate content or prove generation quota/billing is available.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import warnings

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
ALLOWED_BASES = {
    "https://generativelanguage.googleapis.com/v1beta",
    "https://generativelanguage.googleapis.com/v1",
}
SAFE_REASONS = {
    "API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED",
    "API_KEY_IP_ADDRESS_BLOCKED", "API_KEY_HTTP_REFERRER_BLOCKED",
    "ACCESS_TOKEN_TYPE_UNSUPPORTED", "CREDENTIALS_MISSING", "SERVICE_DISABLED",
    "BILLING_DISABLED", "RATE_LIMIT_EXCEEDED", "CONSUMER_INVALID",
}


class SetupError(Exception):
    """An explanation safe to print without exposing credentials or raw bodies."""


def private_config(root: Path) -> bool:
    """Require config.json to be untracked and ignored before adding a secret."""
    def status(args):
        return subprocess.run(
            ["git", *args], cwd=root, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False,
        ).returncode
    return (status(["ls-files", "--error-unmatch", "--", "config.json"]) == 1
            and status(["check-ignore", "-q", "--", "config.json"]) == 0)


def model_endpoint(config: dict) -> str:
    base = config.get("nanobanana2_api_base_url", "https://generativelanguage.googleapis.com/v1beta")
    model = config.get("nanobanana2_model", "gemini-3.1-flash-image-preview")
    if not isinstance(base, str) or base.rstrip("/") not in ALLOWED_BASES:
        raise SetupError("Nonstandard image endpoint: no key was requested or sent. Check the API base URL locally.")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", model):
        raise SetupError("Invalid image model setting. No configuration changed.")
    return base.rstrip("/") + "/models/" + model


def verify_model_access(endpoint: str, key: str) -> None:
    try:
        response = requests.get(
            endpoint, headers={"x-goog-api-key": key},
            timeout=(5, 20), allow_redirects=False,
        )
    except requests.RequestException:
        raise SetupError("Google could not be reached securely. No key saved; no generation attempted.") from None
    try:
        status = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = None
        if status != 200:
            reasons = set()
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                details = body["error"].get("details", [])
                if isinstance(details, list):
                    for detail in details:
                        reason = detail.get("reason") if isinstance(detail, dict) else None
                        if isinstance(reason, str) and reason in SAFE_REASONS:
                            reasons.add(reason)
            hints = {
                400: "Google rejected the key or model request.",
                401: "Google rejected authentication. Check the full Gemini key and its status in AI Studio.",
                403: "Google denied permission. Check the key's Gemini API access and project restrictions.",
                404: "The configured image model is unavailable to this request. Check the model setting.",
                429: "Google reported a quota or rate limit. Check the project quota before retrying.",
            }
            suffix = " Reasons: " + ", ".join(sorted(reasons)) + "." if reasons else ""
            raise SetupError(
                f"Google model-access check: HTTP {status}. "
                + hints.get(status, "Google did not accept the model-access request.")
                + suffix + " No key saved; no generation attempted."
            )
        expected = "models/" + endpoint.rsplit("/", 1)[1]
        if (not isinstance(body, dict) or body.get("name") != expected
                or "generateContent" not in body.get("supportedGenerationMethods", [])):
            raise SetupError("Google returned unexpected model metadata. No key saved; no generation attempted.")
    finally:
        response.close()


def save_key(path: Path, original: bytes, config: dict, key: str) -> None:
    if path.is_symlink() or path.read_bytes() != original:
        raise SetupError("config.json changed during the check. Nothing overwritten; run this helper again.")
    updated = dict(config)
    updated["nanobanana2_api_key"] = key
    descriptor, temporary = tempfile.mkstemp(prefix=".config-key-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(updated, handle, indent=4)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink() or path.read_bytes() != original:
            raise SetupError("config.json changed during the check. Nothing overwritten; run this helper again.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None, *, root=ROOT_DIR) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="After saving, attempt one local preview using configured API quota")
    parser.add_argument("--account", default="HouseOfBigBeans")
    parser.add_argument("--topic", default="A playful Maine Coon cat discovers that a tiny cardboard box is its favorite new bed.")
    args = parser.parse_args(argv)
    root = Path(root)
    try:
        path = root / "config.json"
        if path.is_symlink() or not private_config(root):
            raise SetupError("config.json must be a local, untracked, ignored file. No key requested or saved.")
        original = path.read_bytes()
        config = json.loads(original)
        if not isinstance(config, dict):
            raise SetupError("config.json must contain an object. No file changed.")
        endpoint = model_endpoint(config)
        print("[INFO] Paste your Gemini API key at the hidden prompt. Never paste it into chat.", flush=True)
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("Gemini API key (hidden): ").strip()
        if (not key or not key.isascii() or len(key) > 8192
                or any(c.isspace() or c in "\"'" for c in key)):
            raise SetupError("The key is blank or contains quotes/whitespace. Copy the complete key only; no file changed.")
        print("[INFO] Checking Google model access without generating content...", flush=True)
        verify_model_access(endpoint, key)
        save_key(path, original, config, key)
        del key
        print("[OK] Google model-access check passed. Key saved only in ignored local config.json (owner-only permissions).")
        print("[INFO] Image-generation permission, quota and billing have not been tested.")
    except SetupError as exc:
        print("[FAIL] " + str(exc))
        return 1
    except (KeyboardInterrupt, EOFError, getpass.GetPassWarning):
        print("\n[STOP] Private key entry canceled or unavailable. No key saved.")
        return 1
    except (OSError, ValueError, TypeError):
        print("[FAIL] Local configuration or network response could not be processed. Private details hidden.")
        return 1
    if args.preview:
        print("[INFO] Starting one local preview. This may use paid API quota; no upload or scheduling.", flush=True)
        try:
            return subprocess.run(
                [sys.executable, "-u", str(root / "scripts" / "generate_preview.py"),
                 "--account", args.account, "--topic", args.topic], cwd=root, check=False,
            ).returncode
        except (OSError, KeyboardInterrupt):
            print("[STOP] Preview interrupted or could not start. The verified local key remains saved.")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

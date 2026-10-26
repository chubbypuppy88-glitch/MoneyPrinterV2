#!/usr/bin/env python3
"""Read-only local readiness checks. Never print keys or contact upload services."""
import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"
MODULES = (
    "requests", "termcolor", "schedule", "prettytable", "numpy", "PIL",
    "moviepy", "soundfile", "kittentts", "ollama", "srt_equalizer",
    "assemblyai", "selenium", "selenium_firefox", "webdriver_manager",
)
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def read_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        raise ValueError("config.json must contain a JSON object.")
    return config


def installed(module):
    try:
        return importlib.util.find_spec(module) is not None
    except (ValueError, ImportError):
        return False


def request_models(base_url):
    """Check HTTP status and JSON together; a 404 is not a healthy Ollama server."""
    try:
        with urlopen(base_url.rstrip("/") + "/api/tags", timeout=5) as response:
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
    except Exception as exc:
        return None, type(exc).__name__


def run_checks(config, *, root=ROOT_DIR, offline=False, music=False, require_image_api=True):
    failures = 0

    def report(passed, message, *, optional=False):
        nonlocal failures
        label = "OK" if passed else ("WARN" if optional else "FAIL")
        print(f"[{label}] {message}")
        if not passed and not optional:
            failures += 1

    report(sys.version_info[:2] == (3, 12), "Project target: Python 3.12", optional=True)
    for binary in ("ffmpeg", "ffprobe"):
        report(bool(shutil.which(binary)), f"{binary} available on PATH")
    missing = [name for name in MODULES if not installed(name)]
    report(not missing, "Python dependencies present" if not missing else "Missing modules: " + ", ".join(missing))
    try:
        version = importlib.metadata.version("moviepy")
        report(version == "1.0.3", "MoviePy compatibility: requires pinned version 1.0.3")
    except importlib.metadata.PackageNotFoundError:
        report(False, "MoviePy distribution not installed")

    if require_image_api:
        key = config.get("nanobanana2_api_key") or os.environ.get("GEMINI_API_KEY", "")
        report(isinstance(key, str) and bool(key.strip()), "Image API key configured (value hidden; authentication not tested)")
    else:
        print("[OK] Local-photo preview selected; image API key and quota are not required.")

    model = config.get("ollama_model", "")
    report(isinstance(model, str) and bool(model.strip()), "Ollama model configured; set ollama_model or pass --model")
    if offline:
        print("[WARN] Offline check: Ollama availability was not tested.")
    else:
        base = config.get("ollama_base_url") or "http://127.0.0.1:11434"
        models, problem = request_models(str(base))
        report(models is not None, "Ollama responded with a model list" if problem is None else "Ollama check failed: " + problem)
        if models is not None:
            wanted = model if isinstance(model, str) else ""
            names = {m.removesuffix(":latest") for m in models}
            report(bool(wanted) and wanted.removesuffix(":latest") in names, "Configured Ollama model is installed")

    provider = config.get("stt_provider", "local_whisper")
    if provider == "local_whisper":
        report(installed("faster_whisper"), "Local Whisper dependency available", optional=True)
    elif provider == "third_party_assemblyai":
        report(bool(config.get("assembly_ai_api_key")), "AssemblyAI key configured (value hidden)", optional=True)
    else:
        report(False, "Unknown subtitle provider; captions may fail", optional=True)
    magick = config.get("imagemagick_path", "")
    magick_ok = isinstance(magick, str) and os.path.isfile(magick) and os.access(magick, os.X_OK)
    report(magick_ok, "Configured ImageMagick executable available for captions", optional=True)

    if music:
        songs = Path(root) / "Songs"
        found = songs.is_dir() and any(p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS for p in songs.iterdir())
        report(found, "Background audio available in Songs/")
    else:
        print("[OK] Preview background music disabled; test tones are not needed.")
    print("[INFO] No Firefox, YouTube upload, cross-post, or scheduling checks were run.")
    print(f"[RESULT] {failures} blocking issue(s). Provider authentication and full generation remain unverified.")
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Do not contact the configured Ollama server")
    parser.add_argument("--music", action="store_true", help="Require background audio")
    args = parser.parse_args(argv)
    try:
        config = read_config()
    except (OSError, ValueError):
        print("[FAIL] config.json is missing, unreadable, or invalid. No file was changed.")
        return 1
    return run_checks(config, offline=args.offline, music=args.music)


if __name__ == "__main__":
    sys.exit(main())

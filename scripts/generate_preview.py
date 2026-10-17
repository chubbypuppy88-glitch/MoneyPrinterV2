#!/usr/bin/env python3
"""Generate one local preview. This entrypoint has no upload or cross-post path."""
import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR / "scripts"))
from preflight_local import read_config, run_checks
from preview_diagnostics import report_failure


def load_account(account_name, root=ROOT_DIR):
    """Read an existing local account without copying its private browser profile."""
    path = Path(root) / ".mp" / "youtube.json"
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError("The local YouTube account cache is missing or invalid.") from exc
    accounts = data.get("accounts", []) if isinstance(data, dict) else []
    if not isinstance(accounts, list):
        raise ValueError("The local YouTube account cache is invalid.")
    matches = [a for a in accounts if isinstance(a, dict) and account_name in (a.get("id"), a.get("nickname"))]
    if len(matches) != 1:
        raise ValueError("Choose exactly one existing account by nickname or UUID with --account.")
    account = matches[0]
    if not all(isinstance(account.get(key), str) and account[key].strip() for key in ("id", "nickname", "niche", "language")):
        raise ValueError("The selected account is missing its id, nickname, niche, or language.")
    return account


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="HouseOfBigBeans")
    parser.add_argument("--topic", help="Optional custom video topic")
    parser.add_argument("--model", help="Override the configured Ollama model for this run only")
    parser.add_argument("--music", action="store_true", help="Opt in to local background music; disabled by default")
    parser.add_argument("--check-only", action="store_true", help="Check readiness without generating content")
    args = parser.parse_args(argv)
    try:
        config = read_config(ROOT_DIR / "config.json")
        account = load_account(args.account)
    except (OSError, ValueError):
        print("[FAIL] Check config.json and the selected local account in .mp/youtube.json. No file was changed.")
        return 1
    if args.model:
        config["ollama_model"] = args.model
    result = run_checks(config, root=ROOT_DIR, music=args.music)
    if result or args.check_only:
        return result

    # Delay all model/provider imports until checks pass.
    try:
        from classes.PreviewYouTube import PreviewYouTube as YouTube
        from classes.Tts import TTS
        from llm_provider import select_model

        select_model(config["ollama_model"])
        youtube = YouTube(
            account["id"], account["nickname"], account.get("firefox_profile", ""),
            account["niche"], account["language"], background_music=args.music,
        )
        print("[INFO] Generating a local preview only. Provider calls may use your configured API quota.")
        path = Path(youtube.generate_video(TTS(), topic=args.topic)).resolve()
        metadata_path = path.with_suffix(".json")
        metadata_path.write_text(json.dumps({
            "account": account["nickname"], "preview_only": True,
            "title": youtube.metadata.get("title", ""),
            "description": youtube.metadata.get("description", ""),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] Local preview: {path}")
        print("[OK] Nothing uploaded or scheduled. Review the video and captions before any publishing.")
        return 0
    except Exception as exc:
        report_failure(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

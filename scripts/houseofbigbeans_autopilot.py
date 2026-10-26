#!/usr/bin/env python3
"""Generate a HouseOfBigBeans Short locally and optionally upload it privately."""
import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from generate_preview import load_account
from preflight_local import read_config, run_checks
from preview_diagnostics import report_failure

DEFAULT_TOPIC = (
    "Meet the Maine Coon behind House of Big Beans in a short montage of real photos."
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="HouseOfBigBeans")
    parser.add_argument("--images-dir", default="local_media/houseofbigbeans")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--model", help="Override the configured Ollama model")
    parser.add_argument("--music", action="store_true")
    parser.add_argument(
        "--upload-private", action="store_true",
        help="Upload the finished Short through the official YouTube API as PRIVATE.",
    )
    parser.add_argument("--youtube-client", default="youtube_oauth_client.json")
    parser.add_argument("--youtube-token", default=".youtube_oauth_token.json")
    args = parser.parse_args(argv)

    try:
        config = read_config(ROOT_DIR / "config.json")
        account = load_account(args.account)
    except (OSError, ValueError):
        print("[FAIL] Local config/account cache is missing or invalid.")
        return 1

    images_dir = (ROOT_DIR / args.images_dir).resolve()
    if not images_dir.is_dir():
        print(f"[FAIL] Photo folder not found: {images_dir}")
        return 1

    if args.model:
        config["ollama_model"] = args.model

    result = run_checks(
        config, root=ROOT_DIR, music=args.music, require_image_api=False,
    )
    if result:
        return result

    try:
        from classes.LocalPhotoPreview import LocalPhotoPreview
        from classes.Tts import TTS
        from llm_provider import select_model

        select_model(config["ollama_model"])
        youtube = LocalPhotoPreview(
            account["id"], account["nickname"], account.get("firefox_profile", ""),
            account["niche"], account["language"],
            background_music=args.music, images_dir=str(images_dir),
        )

        print("[AUTO] Local/free path: Ollama -> KittenTTS -> MoviePy/FFmpeg -> script captions.")
        path = Path(youtube.generate_video(TTS(), topic=args.topic)).resolve()
        metadata_path = path.with_suffix(".json")
        metadata_path.write_text(json.dumps({
            "account": account["nickname"],
            "topic": youtube.subject,
            "title": youtube.metadata.get("title", ""),
            "description": youtube.metadata.get("description", ""),
            "video": str(path),
            "private_upload_requested": bool(args.upload_private),
        }, indent=2) + "\n", encoding="utf-8")

        print(f"[OK] Finished local Short: {path}")

        if not args.upload_private:
            print("[OK] Upload skipped. Add --upload-private after one-time YouTube authorization.")
            return 0

        from youtube_api import refresh_access_token, upload_private_video

        client_path = (ROOT_DIR / args.youtube_client).resolve()
        token_path = (ROOT_DIR / args.youtube_token).resolve()
        if not client_path.is_file() or not token_path.is_file():
            print("[FAIL] One-time YouTube authorization is not set up yet.")
            print("[NEXT] Put your TV/Limited Input OAuth client JSON at youtube_oauth_client.json, then run:")
            print("       .venv/bin/python -u scripts/youtube_device_auth.py")
            print(f"[SAFE] Your finished MP4 is preserved at: {path}")
            return 2

        access_token = refresh_access_token(client_path, token_path)
        print("[AUTO] Uploading with YouTube's official API as PRIVATE.")
        url = upload_private_video(
            path,
            title=youtube.metadata.get("title", "HouseOfBigBeans Short"),
            description=youtube.metadata.get("description", ""),
            access_token=access_token,
        )
        print(f"[OK] Private YouTube upload: {url}")
        return 0
    except Exception as exc:
        report_failure(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

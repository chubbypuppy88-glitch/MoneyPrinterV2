#!/usr/bin/env python3
"""One-time free YouTube authorization for unattended private uploads."""
from pathlib import Path
import argparse
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from youtube_api import authorize_device


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", default=str(ROOT_DIR / "youtube_oauth_client.json"))
    parser.add_argument("--token", default=str(ROOT_DIR / ".youtube_oauth_token.json"))
    args = parser.parse_args(argv)
    try:
        authorize_device(args.client, args.token)
        return 0
    except Exception as exc:
        print(f"[FAIL] YouTube authorization failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

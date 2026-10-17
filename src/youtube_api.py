"""Minimal YouTube OAuth + resumable uploader using requests only."""
from __future__ import annotations

from pathlib import Path
import json
import mimetypes
import time
from typing import Any

import requests

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def load_oauth_client(path: str | Path) -> dict[str, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OAuth client file must contain a JSON object.")
    data = payload.get("installed") or payload.get("web") or payload
    if not isinstance(data, dict):
        raise ValueError("OAuth client file is invalid.")
    client_id = str(data.get("client_id") or "").strip()
    client_secret = str(data.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValueError("OAuth client file is missing client_id or client_secret.")
    return {"client_id": client_id, "client_secret": client_secret}


def save_token(path: str | Path, token: dict[str, Any]) -> None:
    target = Path(path)
    target.write_text(json.dumps(token, indent=2) + "\n", encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass


def authorize_device(
    client_path: str | Path,
    token_path: str | Path,
    *,
    session=requests,
) -> dict[str, Any]:
    """Run Google's limited-input device flow and persist refreshable tokens."""
    client = load_oauth_client(client_path)
    response = session.post(
        DEVICE_CODE_URL,
        data={"client_id": client["client_id"], "scope": YOUTUBE_SCOPE},
        timeout=30,
    )
    response.raise_for_status()
    device = response.json()
    device_code = device["device_code"]
    user_code = device["user_code"]
    verification_url = device.get("verification_url") or device.get("verification_uri")
    expires_in = int(device.get("expires_in", 1800))
    interval = max(1, int(device.get("interval", 5)))

    print("\n[AUTH] One-time YouTube authorization")
    print(f"[AUTH] Open: {verification_url}")
    print(f"[AUTH] Enter code: {user_code}")
    print("[AUTH] Waiting for approval...")

    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        token_response = session.post(
            TOKEN_URL,
            data={
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=30,
        )
        data = token_response.json()
        if token_response.ok and data.get("access_token"):
            data["obtained_at"] = int(time.time())
            data["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600))
            save_token(token_path, data)
            print("[OK] YouTube authorization saved locally. Future uploads can refresh automatically.")
            return data

        error = data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error in {"access_denied", "expired_token"}:
            raise RuntimeError(f"YouTube authorization ended: {error}")
        token_response.raise_for_status()

    raise TimeoutError("YouTube authorization code expired before approval.")


def refresh_access_token(
    client_path: str | Path,
    token_path: str | Path,
    *,
    session=requests,
) -> str:
    client = load_oauth_client(client_path)
    token_file = Path(token_path)
    if not token_file.is_file():
        raise FileNotFoundError(
            f"YouTube token not found at {token_file}. Run scripts/youtube_device_auth.py once."
        )
    token = json.loads(token_file.read_text(encoding="utf-8"))
    if not isinstance(token, dict):
        raise ValueError("YouTube token file is invalid.")

    access_token = str(token.get("access_token") or "")
    expires_at = int(token.get("expires_at") or 0)
    if access_token and expires_at > int(time.time()) + 60:
        return access_token

    refresh_token = str(token.get("refresh_token") or "")
    if not refresh_token:
        raise RuntimeError(
            "No refresh token is available. Run scripts/youtube_device_auth.py again."
        )

    response = session.post(
        TOKEN_URL,
        data={
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    response.raise_for_status()
    fresh = response.json()
    token["access_token"] = fresh["access_token"]
    token["expires_in"] = int(fresh.get("expires_in", 3600))
    token["obtained_at"] = int(time.time())
    token["expires_at"] = int(time.time()) + token["expires_in"]
    if fresh.get("refresh_token"):
        token["refresh_token"] = fresh["refresh_token"]
    save_token(token_path, token)
    return token["access_token"]


def upload_private_video(
    video_path: str | Path,
    *,
    title: str,
    description: str,
    access_token: str,
    session=requests,
) -> str:
    """Upload an MP4 with the official resumable protocol and keep it private."""
    video = Path(video_path).resolve()
    if not video.is_file():
        raise FileNotFoundError(video)
    size = video.stat().st_size
    mime = mimetypes.guess_type(video.name)[0] or "video/mp4"

    metadata = {
        "snippet": {
            "title": str(title).strip()[:100] or "HouseOfBigBeans Short",
            "description": str(description).strip(),
        },
        "status": {"privacyStatus": "private"},
    }
    start = session.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": mime,
        },
        json=metadata,
        timeout=30,
    )
    start.raise_for_status()
    location = start.headers.get("Location")
    if not location:
        raise RuntimeError("YouTube did not return a resumable upload URL.")

    with video.open("rb") as handle:
        finish = session.put(
            location,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": mime,
                "Content-Length": str(size),
            },
            data=handle,
            timeout=600,
        )
    finish.raise_for_status()
    body = finish.json()
    video_id = str(body.get("id") or "").strip()
    if not video_id:
        raise RuntimeError("YouTube upload completed without a video id.")
    return f"https://youtu.be/{video_id}"

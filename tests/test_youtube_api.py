import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.youtube_api import load_oauth_client, refresh_access_token, upload_private_video


class FakeResponse:
    def __init__(self, body=None, *, headers=None, ok=True):
        self._body = body or {}
        self.headers = headers or {}
        self.ok = ok
    def json(self):
        return self._body
    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError("http error")


class YouTubeApiTests(unittest.TestCase):
    def test_load_client_accepts_installed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "client.json"
            path.write_text(json.dumps({"installed": {"client_id": "id", "client_secret": "secret"}}))
            self.assertEqual(load_oauth_client(path)["client_id"], "id")

    @patch("src.youtube_api.time.time", return_value=1000)
    def test_refreshes_expired_access_token(self, _time):
        with tempfile.TemporaryDirectory() as tmp:
            client = Path(tmp) / "client.json"
            token = Path(tmp) / "token.json"
            client.write_text(json.dumps({"installed": {"client_id": "id", "client_secret": "secret"}}))
            token.write_text(json.dumps({"access_token": "old", "expires_at": 1, "refresh_token": "refresh"}))
            session = Mock()
            session.post.return_value = FakeResponse({"access_token": "new", "expires_in": 3600})
            self.assertEqual(refresh_access_token(client, token, session=session), "new")
            saved = json.loads(token.read_text())
            self.assertEqual(saved["refresh_token"], "refresh")
            self.assertEqual(saved["access_token"], "new")

    def test_upload_is_always_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"video")
            session = Mock()
            session.post.return_value = FakeResponse(headers={"Location": "https://upload.example/session"})
            session.put.return_value = FakeResponse({"id": "abc123"})
            url = upload_private_video(
                video, title="Title", description="Desc",
                access_token="token", session=session,
            )
            self.assertEqual(url, "https://youtu.be/abc123")
            body = session.post.call_args.kwargs["json"]
            self.assertEqual(body["status"]["privacyStatus"], "private")


if __name__ == "__main__":
    unittest.main()

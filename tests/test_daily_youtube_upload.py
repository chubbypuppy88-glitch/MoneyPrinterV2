import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock
from src.youtube_api import upload_video

class Response:
    def __init__(self,body=None,headers=None): self._body=body or {}; self.headers=headers or {}; self.ok=True
    def json(self): return self._body
    def raise_for_status(self): pass

class YouTubeUploadTests(unittest.TestCase):
    def test_public_upload_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            video=Path(tmp)/"v.mp4"; video.write_bytes(b"video")
            session=Mock(); session.post.return_value=Response(headers={"Location":"https://upload"}); session.put.return_value=Response({"id":"abc"})
            url=upload_video(video,title="Title",description="Desc",access_token="token",privacy_status="public",session=session)
            self.assertEqual(url,"https://youtu.be/abc")
            body=session.post.call_args.kwargs["json"]
            self.assertEqual(body["status"]["privacyStatus"],"public")
            self.assertEqual(body["snippet"]["categoryId"],"15")
    def test_invalid_privacy_rejected(self):
        with self.assertRaises(ValueError):
            upload_video("missing.mp4",title="T",description="D",access_token="x",privacy_status="wrong")

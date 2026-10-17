import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from urllib.error import HTTPError
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_preview
import preflight_local

ACCOUNT = {"id": "id", "nickname": "HouseOfBigBeans", "niche": "cats", "language": "English"}


class PreviewChecksTests(unittest.TestCase):
    def test_account_read_does_not_require_a_firefox_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".mp").mkdir()
            (root / ".mp/youtube.json").write_text(json.dumps({"accounts": [ACCOUNT]}))
            self.assertEqual(generate_preview.load_account("HouseOfBigBeans", root), ACCOUNT)

    def test_missing_account_does_not_create_a_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                generate_preview.load_account("Missing", Path(directory))
            self.assertFalse((Path(directory) / ".mp").exists())

    def test_duplicate_nickname_requires_unambiguous_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".mp").mkdir()
            (root / ".mp/youtube.json").write_text(json.dumps({"accounts": [ACCOUNT, dict(ACCOUNT, id="two")]}))
            with self.assertRaises(ValueError):
                generate_preview.load_account("HouseOfBigBeans", root)

    @patch("preflight_local.urlopen")
    def test_http_failure_is_not_reported_as_a_healthy_service(self, urlopen):
        urlopen.side_effect = HTTPError("https://private.invalid?token=secret", 401, "Unauthorized", {}, None)
        models, error = preflight_local.request_models("https://private.invalid")
        self.assertIsNone(models)
        self.assertEqual(error, "HTTP 401")
        self.assertNotIn("secret", error)

    @patch("preflight_local.urlopen")
    def test_connection_exception_does_not_disclose_url_credentials(self, urlopen):
        urlopen.side_effect = RuntimeError("https://username:secret@example.invalid")
        models, error = preflight_local.request_models("https://example.invalid")
        self.assertIsNone(models)
        self.assertEqual(error, "RuntimeError")

    @patch("preflight_local.installed", return_value=True)
    @patch("preflight_local.shutil.which", return_value="/usr/bin/tool")
    @patch("preflight_local.importlib.metadata.version", return_value="1.0.3")
    @patch("preflight_local.request_models", return_value=(["local:latest"], None))
    def test_ready_report_does_not_echo_api_key(self, *_mocks):
        output = io.StringIO()
        config = {"ollama_model": "local", "nanobanana2_api_key": "do-not-print-this-value"}
        with contextlib.redirect_stdout(output):
            result = preflight_local.run_checks(config)
        self.assertEqual(result, 0)
        self.assertNotIn("do-not-print-this-value", output.getvalue())

    @patch("generate_preview.read_config", return_value={"ollama_model": "local"})
    @patch("generate_preview.load_account", return_value=ACCOUNT)
    @patch("generate_preview.run_checks", return_value=1)
    def test_failed_checks_stop_generation(self, *_mocks):
        self.assertEqual(generate_preview.main([]), 1)

    @patch("generate_preview.read_config", return_value={"ollama_model": "local"})
    @patch("generate_preview.load_account", return_value=ACCOUNT)
    @patch("generate_preview.run_checks", return_value=0)
    def test_preview_never_calls_upload_and_disables_music_by_default(self, *_mocks):
        youtube = Mock()
        youtube.metadata = {"title": "Cats", "description": "Preview"}
        factory = Mock(return_value=youtube)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preview.mp4"
            youtube.generate_video.return_value = str(path)
            modules = {
                "classes.YouTube": types.SimpleNamespace(YouTube=factory),
                "classes.Tts": types.SimpleNamespace(TTS=Mock()),
                "llm_provider": types.SimpleNamespace(select_model=Mock()),
            }
            with patch.dict(sys.modules, modules), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(generate_preview.main(["--topic", "Cats"]), 0)
            youtube.upload_video.assert_not_called()
            self.assertFalse(factory.call_args.kwargs["background_music"])
            self.assertTrue(json.loads(path.with_suffix(".json").read_text())["preview_only"])


if __name__ == "__main__":
    unittest.main()

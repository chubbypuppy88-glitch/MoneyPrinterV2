import contextlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import configure_image_key as helper

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/test-image-model"
KEY = "private-test-key-not-a-real-credential"


class ImageKeySetupTests(unittest.TestCase):
    def response(self, status=200, body=None):
        response = Mock(status_code=status)
        response.json.return_value = body if body is not None else {
            "name": "models/test-image-model",
            "supportedGenerationMethods": ["generateContent"],
        }
        return response

    def test_official_endpoint_only(self):
        for base in ("http://generativelanguage.googleapis.com/v1beta", "https://example.invalid", "https://generativelanguage.googleapis.com.evil.invalid/v1beta", "https://generativelanguage.googleapis.com/v1beta?key=hidden"):
            with self.subTest(base=base), self.assertRaises(helper.SetupError):
                helper.model_endpoint({"nanobanana2_api_base_url": base})

    def test_model_cannot_inject_path_or_query(self):
        for model in ("../bad", "x?key=y", "models/x", None):
            with self.subTest(model=model), self.assertRaises(helper.SetupError):
                helper.model_endpoint({"nanobanana2_model": model})

    def test_success_sends_key_only_in_header_without_redirects(self):
        response = self.response()
        with patch.object(helper.requests, "get", return_value=response) as request:
            helper.verify_model_access(ENDPOINT, KEY)
        request.assert_called_once_with(ENDPOINT, headers={"x-goog-api-key": KEY}, timeout=(5, 20), allow_redirects=False)
        response.close.assert_called_once()

    def test_http_errors_never_expose_private_response_text(self):
        for status in (400, 401, 403, 404, 429, 500, 302):
            response = self.response(status, {"error": {"message": KEY, "details": [{"reason": "API_KEY_INVALID"}, {"reason": KEY}]}})
            with self.subTest(status=status), patch.object(helper.requests, "get", return_value=response):
                with self.assertRaises(helper.SetupError) as result:
                    helper.verify_model_access(ENDPOINT, KEY)
                self.assertNotIn(KEY, str(result.exception))
                self.assertIn(str(status), str(result.exception))
                self.assertIn("API_KEY_INVALID", str(result.exception))
                response.close.assert_called_once()

    def test_network_failure_does_not_echo_key(self):
        with patch.object(helper.requests, "get", side_effect=helper.requests.RequestException(KEY)):
            with self.assertRaises(helper.SetupError) as result:
                helper.verify_model_access(ENDPOINT, KEY)
        self.assertNotIn(KEY, str(result.exception))

    def test_unexpected_model_is_not_saved(self):
        response = self.response(body={"name": "models/other-model", "supportedGenerationMethods": ["generateContent"]})
        with patch.object(helper.requests, "get", return_value=response), self.assertRaises(helper.SetupError):
            helper.verify_model_access(ENDPOINT, KEY)

    def test_private_save_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            old = {"nanobanana2_api_key": "old", "headless": True, "other": {"value": 42}}
            original = json.dumps(old).encode()
            path.write_bytes(original)
            helper.save_key(path, original, old, KEY)
            saved = json.loads(path.read_bytes())
            self.assertEqual(saved, {**old, "nanobanana2_api_key": KEY})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["config.json"])

    def test_concurrent_edit_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text('{"new": true}')
            with self.assertRaises(helper.SetupError):
                helper.save_key(path, b"{}", {}, KEY)
            self.assertEqual(path.read_text(), '{"new": true}')

    def test_tracked_config_is_rejected(self):
        with patch.object(helper.subprocess, "run", return_value=Mock(returncode=0)) as run:
            self.assertFalse(helper.private_config(Path(".")))
        run.assert_called_once()

    def test_untracked_but_not_ignored_config_is_rejected(self):
        with patch.object(helper.subprocess, "run", side_effect=[Mock(returncode=1), Mock(returncode=1)]):
            self.assertFalse(helper.private_config(Path(".")))

    def test_git_failure_is_rejected(self):
        with patch.object(helper.subprocess, "run", return_value=Mock(returncode=128)):
            self.assertFalse(helper.private_config(Path(".")))

    def run_main(self, *, failure=False, preview=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "config.json"
            original = b'{"nanobanana2_model": "test-image-model", "nanobanana2_api_key": "old"}'
            path.write_bytes(original)
            output = io.StringIO()
            with patch.object(helper, "private_config", return_value=True), patch.object(helper.getpass, "getpass", return_value=KEY), patch.object(helper, "verify_model_access", side_effect=helper.SetupError("Authentication rejected") if failure else None) as verify, patch.object(helper.subprocess, "run", return_value=Mock(returncode=0)) as run, contextlib.redirect_stdout(output):
                result = helper.main(["--preview"] if preview else [], root=root)
            self.assertNotIn(KEY, output.getvalue())
            verify.assert_called_once_with(ENDPOINT, KEY)
            if failure:
                self.assertEqual(result, 1)
                self.assertEqual(path.read_bytes(), original)
                run.assert_not_called()
            else:
                self.assertEqual(result, 0)
                self.assertEqual(json.loads(path.read_bytes())["nanobanana2_api_key"], KEY)
                if preview:
                    run.assert_called_once()
                    command = run.call_args.args[0]
                    self.assertNotIn(KEY, command)
                    self.assertEqual(command[2], str(root / "scripts" / "generate_preview.py"))
                    self.assertNotIn("--music", command)
                else:
                    run.assert_not_called()

    def test_failed_auth_does_not_save_or_generate(self):
        self.run_main(failure=True, preview=True)

    def test_save_only_never_starts_preview(self):
        self.run_main()

    def test_preview_runs_only_after_validated_save(self):
        self.run_main(preview=True)

    def test_no_echo_fallback_stops_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text("{}")
            with patch.object(helper, "private_config", return_value=True), patch.object(helper.getpass, "getpass", side_effect=helper.getpass.GetPassWarning("no terminal")), patch.object(helper, "verify_model_access") as verify, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(helper.main([], root=root), 1)
            verify.assert_not_called()
            self.assertEqual((root / "config.json").read_text(), "{}")


if __name__ == "__main__":
    unittest.main()

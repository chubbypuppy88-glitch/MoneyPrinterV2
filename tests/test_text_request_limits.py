"""Offline regressions for text wait limits and formerly recursive retries."""
import ast
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]


def load_provider():
    spec = importlib.util.spec_from_file_location("bounded_provider_under_test", ROOT / "src/llm_provider.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        "ollama": types.SimpleNamespace(Client=Mock()),
        "config": types.SimpleNamespace(get_ollama_base_url=lambda: "http://127.0.0.1:11434"),
    }):
        spec.loader.exec_module(module)
    return module


def load_text_methods():
    source = ast.parse((ROOT / "src/classes/YouTube.py").read_text())
    cls = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "YouTube")
    wanted = {"generate_script", "generate_metadata"}
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = {"re": __import__("re"), "get_script_sentence_length": lambda: 4, "warning": Mock()}
    exec(compile(module, str(ROOT / "src/classes/YouTube.py"), "exec"), namespace)
    instance = namespace["YouTube"]()
    instance.subject = "A cat finds a box"
    instance.language = "English"
    instance.script = "A short cat story."
    return instance


class TextRequestLimitsTests(unittest.TestCase):
    def setUp(self):
        self.module = load_provider()
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def test_client_sets_inactivity_and_connect_timeouts(self):
        self.module._client()
        options = self.module.ollama.Client.call_args.kwargs
        self.assertEqual(options["timeout"].read, 120.0)
        self.assertEqual(options["timeout"].connect, 10.0)

    def test_chat_has_output_cap_and_returns_trimmed_text(self):
        client = Mock()
        client.chat.return_value = {"message": {"content": "  Small cat story.  "}}
        self.module.select_model("llama3.2:1b")
        with patch.object(self.module, "_client", return_value=client):
            result = self.module.generate_text("private input")
        self.assertEqual(result, "Small cat story.")
        self.assertEqual(client.chat.call_args.kwargs["options"]["num_predict"], 512)
        self.assertFalse(client.chat.call_args.kwargs["stream"])
        client.close.assert_called_once()
        self.assertNotIn("private input", self.output.getvalue())

    def test_missing_model_does_not_contact_server(self):
        with patch.object(self.module, "_client") as create:
            with self.assertRaises(RuntimeError):
                self.module.generate_text("input")
        create.assert_not_called()

    def test_model_override_is_preserved(self):
        client = Mock()
        client.chat.return_value = {"message": {"content": "result"}}
        self.module.select_model("first")
        with patch.object(self.module, "_client", return_value=client):
            self.module.generate_text("input", model_name="override")
        self.assertEqual(client.chat.call_args.kwargs["model"], "override")

    def test_timeout_has_no_retry_and_does_not_echo_private_exception(self):
        client = Mock()
        client.chat.side_effect = httpx.ReadTimeout("secret-token-and-provider-url")
        with patch.object(self.module, "_client", return_value=client):
            with self.assertRaises(TimeoutError) as raised:
                self.module.generate_text("input", "local-model")
        client.chat.assert_called_once()
        client.close.assert_called_once()
        self.assertNotIn("secret-token", self.output.getvalue() + str(raised.exception))

    def test_empty_content_is_an_error(self):
        client = Mock()
        client.chat.return_value = {"message": {"content": " \n "}}
        with patch.object(self.module, "_client", return_value=client):
            with self.assertRaises(RuntimeError):
                self.module.generate_text("input", "local-model")
        client.close.assert_called_once()

    def test_cleanup_failure_does_not_mask_success(self):
        client = Mock()
        client.chat.return_value = {"message": {"content": "result"}}
        client.close.side_effect = RuntimeError("close failed")
        with patch.object(self.module, "_client", return_value=client):
            self.assertEqual(self.module.generate_text("input", "local-model"), "result")

    def test_model_listing_releases_client(self):
        client = Mock()
        client.list.return_value = types.SimpleNamespace(models=[types.SimpleNamespace(model="z"), types.SimpleNamespace(model="a")])
        with patch.object(self.module, "_client", return_value=client):
            self.assertEqual(self.module.list_models(), ["a", "z"])
        client.close.assert_called_once()

    def test_oversized_script_fails_without_recursive_retry(self):
        youtube = load_text_methods()
        youtube.generate_response = Mock(return_value="x" * 5001)
        with self.assertRaises(RuntimeError):
            youtube.generate_script()
        youtube.generate_response.assert_called_once()

    def test_empty_script_fails_before_later_stages(self):
        youtube = load_text_methods()
        youtube.generate_response = Mock(return_value="   ")
        with self.assertRaises(RuntimeError):
            youtube.generate_script()
        youtube.generate_response.assert_called_once()

    def test_long_title_is_shortened_without_recursive_retry(self):
        youtube = load_text_methods()
        youtube.generate_response = Mock(side_effect=["Playful cat " * 100, "Description."])
        result = youtube.generate_metadata()
        self.assertGreater(len(result["title"]), 0)
        self.assertLessEqual(len(result["title"]), 100)
        self.assertEqual(youtube.generate_response.call_count, 2)

    def test_unbroken_long_title_stays_bounded(self):
        youtube = load_text_methods()
        youtube.generate_response = Mock(side_effect=["x" * 500, "Description."])
        self.assertEqual(len(youtube.generate_metadata()["title"]), 100)
        self.assertEqual(youtube.generate_response.call_count, 2)

    def test_empty_title_stops_before_description(self):
        youtube = load_text_methods()
        youtube.generate_response = Mock(return_value="   ")
        with self.assertRaises(RuntimeError):
            youtube.generate_metadata()
        youtube.generate_response.assert_called_once()


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preview_diagnostics import describe_failure, report_failure, ROOT_DIR


class PreviewDiagnosticTests(unittest.TestCase):
    def test_invalid_image_prompts_are_identified(self):
        error = RuntimeError("The language model did not return usable image prompts after 3 attempts.")
        self.assertEqual(describe_failure(error)["code"], "INVALID_IMAGE_PROMPTS")

    def test_missing_model_is_distinguished(self):
        error = RuntimeError("No Ollama model selected. Call select_model() first or pass model_name.")
        self.assertEqual(describe_failure(error)["code"], "NO_MODEL_SELECTED")

    def test_unknown_message_and_url_are_not_printed(self):
        error = RuntimeError("api_key=private-key https://user:private-pass@example.invalid/private-token")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            report_failure(error)
        for private in ("private-key", "private-pass", "private-token", "example.invalid"):
            self.assertNotIn(private, output.getvalue())
        self.assertIn("UNCLASSIFIED_ERROR", output.getvalue())

    def test_exact_match_does_not_echo_injected_suffix(self):
        error = RuntimeError("The generated voiceover is empty. SECRET")
        self.assertEqual(describe_failure(error)["code"], "UNCLASSIFIED_ERROR")
        self.assertNotIn("SECRET", str(describe_failure(error)))

    def test_nested_known_error_is_reported(self):
        inner = RuntimeError("The generated voiceover is empty.")
        outer = RuntimeError("private wrapper text")
        outer.__cause__ = inner
        details = describe_failure(outer)
        self.assertEqual(details["code"], "EMPTY_VOICEOVER")
        self.assertNotIn("private wrapper text", str(details))

    def test_exception_cycle_is_bounded(self):
        error = RuntimeError("secret")
        error.__cause__ = error
        self.assertEqual(len(describe_failure(error)["types"]), 1)

    def test_numeric_http_status_is_retained_without_body(self):
        error = RuntimeError("private response body")
        error.status_code = 403
        self.assertEqual(describe_failure(error)["http_status"], 403)
        self.assertNotIn("private response", str(describe_failure(error)))

    def test_untrusted_http_status_is_not_printed(self):
        error = RuntimeError("secret")
        error.status_code = "token-secret"
        self.assertIsNone(describe_failure(error)["http_status"])

    def test_traceback_reports_stage_but_not_source_or_locals(self):
        namespace = {}
        code = compile("def generate_script():\n    private_value = 'SENSITIVE_LOCAL'\n    raise RuntimeError('SENSITIVE_MESSAGE')\n",
                       str(ROOT_DIR / "src/classes/YouTube.py"), "exec")
        exec(code, namespace)
        try:
            namespace["generate_script"]()
        except RuntimeError as error:
            details = describe_failure(error)
        self.assertEqual(details["stage"], "script generation")
        self.assertIn("src/classes/YouTube.py:3 in generate_script", details["locations"])
        self.assertNotIn("SENSITIVE", str(details))
        self.assertNotIn(str(ROOT_DIR), str(details))

    def test_oom_is_identified(self):
        self.assertEqual(describe_failure(MemoryError("private"))["code"], "OUT_OF_MEMORY")

    def test_connection_failure_is_identified(self):
        self.assertEqual(describe_failure(ConnectionRefusedError("secret-url"))["code"], "PROVIDER_CONNECTION")

    def test_suppressed_context_is_not_examined(self):
        outer = ValueError("private")
        outer.__context__ = RuntimeError("The generated voiceover is empty.")
        outer.__suppress_context__ = True
        self.assertEqual(describe_failure(outer)["code"], "UNCLASSIFIED_ERROR")


if __name__ == "__main__":
    unittest.main()

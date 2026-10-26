import ast
import contextlib
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

from test_youtube_custom_topic import YouTube, _make_youtube

ROOT = Path(__file__).resolve().parents[1]


class YouTubeSafetyTests(unittest.TestCase):
    @patch("classes.YouTube.GeckoDriverManager")
    @patch("classes.YouTube.webdriver.Firefox")
    def test_constructor_does_not_start_firefox(self, firefox, manager):
        youtube = YouTube("id", "name", "", "cats", "English", background_music=False)
        self.assertIsNone(youtube.browser)
        self.assertFalse(youtube.background_music)
        firefox.assert_not_called()
        manager.assert_not_called()

    @patch("classes.YouTube.get_script_sentence_length", return_value=4)
    def test_prompt_count_is_not_based_on_script_character_count(self, _length):
        youtube = YouTube.__new__(YouTube)
        youtube.subject = "Cats"
        youtube.script = "Long script. " * 100
        youtube.generate_response = Mock(return_value=json.dumps(["cat scene"] * 100))
        self.assertEqual(len(youtube.generate_prompts()), 4)
        self.assertIn("exactly 4", youtube.generate_response.call_args.args[0])

    @patch("classes.YouTube.get_script_sentence_length", return_value=999)
    def test_prompt_count_has_a_hard_cap(self, _length):
        youtube = YouTube.__new__(YouTube)
        youtube.subject, youtube.script = "Cats", "A cat."
        youtube.generate_response = Mock(return_value=json.dumps(["cat"] * 100))
        self.assertEqual(len(youtube.generate_prompts()), 8)

    @patch("classes.YouTube.get_script_sentence_length", return_value=4)
    def test_invalid_prompts_stop_after_three_attempts(self, _length):
        youtube = YouTube.__new__(YouTube)
        youtube.subject, youtube.script = "Cats", "A cat."
        youtube.generate_response = Mock(return_value="not JSON")
        with self.assertRaises(RuntimeError):
            youtube.generate_prompts()
        self.assertEqual(youtube.generate_response.call_count, 3)

    @patch("classes.YouTube.get_script_sentence_length", return_value=4)
    def test_multiline_json_and_empty_items(self, _length):
        youtube = YouTube.__new__(YouTube)
        youtube.subject, youtube.script = "Cats", "A cat."
        youtube.generate_response = Mock(return_value='Result:\n[" cat ", "", null, 7]\n')
        self.assertEqual(youtube.generate_prompts(), ["cat"])

    @patch("classes.YouTube.get_verbose", return_value=False)
    def test_failed_images_stop_before_voiceover_or_render(self, _verbose):
        youtube = _make_youtube()
        youtube.images = ["stale-image.png"]
        youtube.generate_image = Mock(return_value=None)
        with self.assertRaises(RuntimeError):
            youtube.generate_video(Mock(), topic="Cats")
        self.assertEqual(youtube.images, [])
        youtube.generate_script_to_speech.assert_not_called()
        youtube.combine.assert_not_called()

    def test_failed_upload_handles_a_browser_that_never_opened(self):
        youtube = YouTube("id", "name", "", "cats", "English")
        youtube.get_channel_id = Mock(side_effect=ValueError("No local profile"))
        self.assertFalse(youtube.upload_video())
        self.assertIsNone(youtube.browser)

    def test_root_is_based_on_the_source_location(self):
        import config
        self.assertEqual(Path(config.ROOT_DIR), ROOT)

    def test_menu_bad_input_and_listing_do_not_start_tts_or_clean_files(self):
        # Execute the real main() body while replacing its unrelated import-time providers.
        tree = ast.parse((ROOT / "src/main.py").read_text())
        main_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        module = ast.Module(body=[main_node], type_ignores=[])
        account = {"id": "id", "nickname": "Cats", "firefox_profile": "", "niche": "cats", "language": "English"}
        youtube = Mock()
        youtube.get_videos.return_value = []
        tts, cleanup, warning = Mock(), Mock(), Mock()
        questions = iter(["1", "ls -la", "3", "5"])
        namespace = {
            "info": Mock(), "warning": warning, "error": Mock(),
            "OPTIONS": ["YouTube"], "YOUTUBE_OPTIONS": ["one", "two", "three", "four", "five"],
            "input": lambda message: "1", "question": lambda message: next(questions),
            "get_accounts": lambda provider: [account], "PrettyTable": Mock(),
            "colored": lambda value, color: value, "YouTube": Mock(return_value=youtube),
            "TTS": tts, "rem_temp_files": cleanup, "get_verbose": lambda: False,
        }
        exec(compile(module, "src/main.py", "exec"), namespace)
        with contextlib.redirect_stdout(io.StringIO()):
            namespace["main"]()
        tts.assert_not_called()
        cleanup.assert_not_called()
        youtube.get_videos.assert_called_once()
        self.assertTrue(any("menu number" in str(call) for call in warning.call_args_list))


if __name__ == "__main__":
    unittest.main()

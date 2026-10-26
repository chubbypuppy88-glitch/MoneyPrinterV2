import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

# Reuse the project's optional-provider stubs, but exercise the real pipeline.
from test_youtube_custom_topic import YouTube
from classes.PreviewYouTube import PreviewYouTube


class PreviewPromptPipelineTests(unittest.TestCase):
    @patch("classes.PreviewYouTube.get_script_sentence_length", return_value=4)
    def test_prompt_generation_never_calls_ollama(self, _length):
        preview = PreviewYouTube("id", "HouseOfBigBeans", "", "cats", "English", background_music=False)
        preview.subject = "A Maine Coon finds a box"
        preview.script = "A cat sees a box. The cat climbs inside."
        preview.generate_response = Mock(side_effect=AssertionError("No JSON call allowed"))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            prompts = preview.generate_prompts()
        self.assertEqual(len(prompts), 2)
        self.assertEqual(preview.image_prompts, prompts)
        preview.generate_response.assert_not_called()
        self.assertIsNone(preview.browser)
        self.assertIn("no Ollama JSON", output.getvalue())

    @patch("classes.YouTube.get_verbose", return_value=False)
    @patch("classes.YouTube.get_script_sentence_length", return_value=4)
    @patch("classes.PreviewYouTube.get_script_sentence_length", return_value=4)
    def test_real_pipeline_reaches_images_voiceover_and_render_without_json(self, *_patches):
        preview = PreviewYouTube("id", "HouseOfBigBeans", "", "cats", "English", background_music=False)
        # Three responses are enough: script, title, description. Any extra LLM
        # request (including for prompts) fails the test with StopIteration.
        preview.generate_response = Mock(side_effect=[
            "A Maine Coon sees a box. It climbs in. It curls up. It naps.",
            "A Maine Coon Finds the Perfect Bed", "A cat enjoys a cardboard box.",
        ])
        preview.generate_image = Mock(side_effect=lambda prompt: preview.images.append("fixture.png"))
        preview.generate_script_to_speech = Mock()
        preview.combine = Mock(return_value="preview.mp4")
        preview.upload_video = Mock(side_effect=AssertionError("No upload allowed"))
        with tempfile.TemporaryDirectory() as directory:
            with patch("classes.YouTube.ROOT_DIR", directory), contextlib.redirect_stdout(io.StringIO()):
                result = preview.generate_video(Mock(), topic="A Maine Coon discovers a box")
            self.assertTrue((Path(directory) / ".mp").is_dir())
        self.assertEqual(result, "preview.mp4")
        self.assertEqual(preview.generate_response.call_count, 3)
        self.assertEqual(preview.generate_image.call_count, 4)
        preview.generate_script_to_speech.assert_called_once()
        preview.combine.assert_called_once()
        preview.upload_video.assert_not_called()
        self.assertIsNone(preview.browser)

    @patch("classes.PreviewYouTube.get_script_sentence_length", return_value=4)
    def test_empty_script_cannot_silently_become_an_image_prompt(self, _length):
        preview = PreviewYouTube("id", "name", "", "cats", "English")
        preview.subject, preview.script = "Cats", " "
        with self.assertRaises(ValueError):
            preview.generate_prompts()

    def test_preview_only_overrides_prompt_generation(self):
        self.assertIs(PreviewYouTube.generate_video, YouTube.generate_video)
        self.assertIs(PreviewYouTube.combine, YouTube.combine)
        self.assertIsNot(PreviewYouTube.generate_prompts, YouTube.generate_prompts)


if __name__ == "__main__":
    unittest.main()

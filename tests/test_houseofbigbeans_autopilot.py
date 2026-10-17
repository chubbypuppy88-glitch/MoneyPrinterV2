import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from src.script_captions import build_ass, _caption_chunks
from src.classes.LocalPhotoPreview import LocalPhotoPreview


class ScriptCaptionTests(unittest.TestCase):
    def test_caption_chunks_follow_script_sentences(self):
        self.assertEqual(
            _caption_chunks("One. Two! Three?"),
            ["One.", "Two!", "Three?"],
        )

    def test_ass_uses_full_duration_and_vertical_style(self):
        ass = build_ass("One sentence. Another sentence.", 14.0)
        self.assertIn("PlayResX: 1080", ass)
        self.assertIn("PlayResY: 1920", ass)
        self.assertIn("0:00:00.00,0:00:07.00", ass)
        self.assertIn("0:00:07.00,0:00:14.00", ass)

    def test_empty_caption_script_is_rejected(self):
        with self.assertRaises(ValueError):
            build_ass("   ", 10)


class LocalPhotoNarrationTests(unittest.TestCase):
    def test_local_photo_prompt_forbids_invented_box_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview = LocalPhotoPreview(
                "id", "HouseOfBigBeans", "", "Maine Coon cats", "English",
                background_music=False, images_dir=tmp,
            )
            captured = []
            def fake(prompt):
                captured.append(prompt)
                return "Meet the Maine Coon behind House of Big Beans. Fluffy and curious. Always supervising the room. This little lion owns the place."
            preview.generate_response = fake
            with patch("src.classes.LocalPhotoPreview.get_script_sentence_length", return_value=4):
                script = preview.generate_script()
            self.assertIn("House of Big Beans", script)
            self.assertIn("Do not invent a cardboard box", captured[0])


if __name__ == "__main__":
    unittest.main()

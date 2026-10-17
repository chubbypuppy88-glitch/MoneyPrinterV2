import tempfile
from pathlib import Path
import unittest

# Register lightweight optional-provider stubs before importing the real local class.
from test_youtube_custom_topic import YouTube  # noqa: F401
from classes.LocalPhotoPreview import LocalPhotoPreview


class LocalPhotoPreviewTests(unittest.TestCase):
    def make_preview(self, directory):
        return LocalPhotoPreview(
            "id", "nick", "", "cats", "English",
            background_music=False, images_dir=str(directory),
        )

    def test_uses_supported_local_images_in_sorted_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.jpeg").write_bytes(b"b")
            (root / "a.png").write_bytes(b"a")
            (root / "ignore.txt").write_text("x")
            preview = self.make_preview(root)
            prompts = preview.generate_prompts()
            self.assertEqual([Path(p).name for p in prompts], ["a.png", "b.jpeg"])
            self.assertEqual(preview.generate_image(prompts[0]), prompts[0])
            self.assertEqual(preview.images, [prompts[0]])

    def test_rejects_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview = self.make_preview(tmp)
            with self.assertRaisesRegex(RuntimeError, "No supported local images"):
                preview.generate_prompts()


if __name__ == "__main__":
    unittest.main()

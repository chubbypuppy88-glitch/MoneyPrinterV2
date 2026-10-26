import base64
import datetime as dt
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_houseofbigbeans as daily


class DailyHouseOfBigBeansTests(unittest.TestCase):
    def test_topics_change_day_to_day(self):
        self.assertNotEqual(
            daily.choose_topic(dt.date(2026, 10, 25))[1],
            daily.choose_topic(dt.date(2026, 10, 26))[1],
        )

    def test_four_scene_prompts_keep_same_cat(self):
        prompts = daily.scene_prompts("topic", "One. Two. Three. Four.")
        self.assertEqual(len(prompts), 4)
        self.assertTrue(all("SAME silver Maine Coon cat" in p for p in prompts))

    def _jpeg_b64(self):
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), (120, 130, 140)).save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def test_free_provider_needs_no_api_key(self):
        fake = Mock()
        fake.json.return_value = {"data": [{"b64_json": self._jpeg_b64()}]}
        fake.raise_for_status = Mock()
        with tempfile.TemporaryDirectory() as tmp, patch(
            "daily_houseofbigbeans.requests.post", return_value=fake
        ) as post:
            destination = Path(tmp) / "x.jpg"
            daily.generate_image(
                "cat", destination, api_key="", model="pollinations/flux", seed=7
            )
            self.assertTrue(destination.is_file())
            headers = post.call_args.kwargs["headers"]
            self.assertNotIn("Authorization", headers)
            body = post.call_args.kwargs["json"]
            self.assertEqual(body["size"], "720x1280")
            self.assertEqual(body["model"], "pollinations/flux")
            self.assertEqual(body["seed"], 7)
            self.assertEqual(body["response_format"], "url")

    def test_optional_key_is_forwarded_when_present(self):
        fake = Mock()
        fake.json.return_value = {"data": [{"b64_json": self._jpeg_b64()}]}
        fake.raise_for_status = Mock()
        with tempfile.TemporaryDirectory() as tmp, patch(
            "daily_houseofbigbeans.requests.post", return_value=fake
        ) as post:
            daily.generate_image(
                "cat", Path(tmp) / "x.jpg",
                api_key="optional-key", model="pollinations/flux", seed=8,
            )
            self.assertEqual(
                post.call_args.kwargs["headers"]["Authorization"],
                "Bearer optional-key",
            )


if __name__ == "__main__":
    unittest.main()

import datetime as dt
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_houseofbigbeans as daily

class DailyHouseOfBigBeansTests(unittest.TestCase):
    def test_topics_change_day_to_day(self):
        self.assertNotEqual(daily.choose_topic(dt.date(2026,10,25))[1], daily.choose_topic(dt.date(2026,10,26))[1])
    def test_four_scene_prompts_keep_same_cat(self):
        prompts=daily.scene_prompts("topic","One. Two. Three. Four.")
        self.assertEqual(len(prompts),4)
        self.assertTrue(all("SAME silver Maine Coon cat" in p for p in prompts))
    def test_image_generation_requires_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                daily.generate_image("x",Path(tmp)/"x.jpg",api_key="",model="flux",seed=1)
    def test_provider_request_uses_vertical_size_and_auth(self):
        fake=Mock(); fake.headers={"Content-Type":"image/jpeg"}; fake.content=b"not-an-image"; fake.raise_for_status=Mock()
        with tempfile.TemporaryDirectory() as tmp, patch("daily_houseofbigbeans.requests.get",return_value=fake) as get:
            with self.assertRaises(Exception):
                daily.generate_image("cat",Path(tmp)/"x.jpg",api_key="sk_test",model="flux",seed=7)
            self.assertEqual(get.call_args.kwargs["params"]["width"],720)
            self.assertEqual(get.call_args.kwargs["params"]["height"],1280)
            self.assertEqual(get.call_args.kwargs["headers"]["Authorization"],"Bearer sk_test")

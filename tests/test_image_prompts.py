import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from image_prompts import build_scene_prompts


class ScenePromptTests(unittest.TestCase):
    def test_four_sentences_produce_four_ordered_prompts(self):
        sentences = ["The cat sees a box.", "It sniffs the edge.", "It climbs inside.", "It falls asleep."]
        prompts = build_scene_prompts("Maine Coon discovers a box", " ".join(sentences), 4)
        self.assertEqual(len(prompts), 4)
        for index, (sentence, prompt) in enumerate(zip(sentences, prompts), 1):
            self.assertIn(sentence, prompt)
            self.assertIn("Maine Coon discovers a box", prompt)
            self.assertIn(f"Scene {index} of 4", prompt)
            self.assertIn("9:16", prompt)

    def test_sentence_groups_preserve_all_source_text_in_order(self):
        sentences = [f"Original sentence {number}." for number in range(11)]
        prompts = build_scene_prompts("Original topic", " ".join(sentences), 4)
        body = "\n".join(prompts)
        positions = [body.index(sentence) for sentence in sentences]
        self.assertEqual(positions, sorted(positions))
        for sentence in sentences:
            self.assertEqual(body.count(sentence), 1)

    def test_short_script_does_not_duplicate_paid_image_requests(self):
        self.assertEqual(len(build_scene_prompts("Cats", "A cat rests.", 4)), 1)

    def test_no_sentence_punctuation_is_still_usable(self):
        self.assertEqual(len(build_scene_prompts("Cats", "A cat rests by a box", 4)), 1)

    def test_hard_cap_is_eight(self):
        self.assertEqual(len(build_scene_prompts("Cats", "A cat. " * 20, 1000)), 8)

    def test_nonpositive_scene_counts_are_clamped_to_one(self):
        for count in (0, -1):
            with self.subTest(count=count):
                self.assertEqual(len(build_scene_prompts("Cats", "A cat. A box.", count)), 1)

    def test_newlines_and_whitespace_are_normalized(self):
        prompts = build_scene_prompts(" A  Maine\n Coon ", " A cat\n\n A box\r\n A nap ", 4)
        self.assertEqual(len(prompts), 3)
        self.assertTrue(all("Video topic: A Maine Coon" in prompt for prompt in prompts))

    def test_cjk_punctuation_does_not_require_spaces(self):
        prompts = build_scene_prompts("\u732b", "\u732b\u6765\u4e86\u3002\u732b\u7761\u4e86\u3002", 4)
        self.assertEqual(len(prompts), 2)

    def test_quotes_and_brackets_are_plain_script_text(self):
        script = 'The cat sees [a box] and hears "hello".'
        self.assertIn(script, build_scene_prompts("Cat's day", script)[0])

    def test_empty_or_nontext_input_is_rejected(self):
        for value in ("", " \n ", None, 17):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_scene_prompts(value, "A cat.")
                with self.assertRaises(ValueError):
                    build_scene_prompts("Cats", value)

    def test_invalid_scene_count_is_rejected(self):
        for count in (True, "4", None, 2.5):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    build_scene_prompts("Cats", "A cat.", count)

    def test_same_input_produces_same_prompts(self):
        args = ("Cats", "A box. A cat. A nap.", 3)
        self.assertEqual(build_scene_prompts(*args), build_scene_prompts(*args))


if __name__ == "__main__":
    unittest.main()

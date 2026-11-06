"""caption.py takes its numbers from platform.json, and survives without it."""

import json
import os
import tempfile
import unittest

from _load import ROOT, load

PLATFORM = os.path.join(ROOT, "platform.json")


def load_caption(env_path=None):
    old = os.environ.get("IG_PLATFORM_JSON")
    try:
        if env_path is None:
            os.environ.pop("IG_PLATFORM_JSON", None)
        else:
            os.environ["IG_PLATFORM_JSON"] = env_path
        return load("ig-caption/caption.py", name="caption_under_test")
    finally:
        if old is None:
            os.environ.pop("IG_PLATFORM_JSON", None)
        else:
            os.environ["IG_PLATFORM_JSON"] = old


class PlatformFile(unittest.TestCase):
    def test_file_is_dated(self):
        with open(PLATFORM, encoding="utf-8") as fh:
            data = json.load(fh)
        facts = data["facts"]
        for key in ("hashtag_cap", "caption_limit", "feed_truncation", "carousel",
                    "reel_safe_zone", "story_safe_zone", "reel_max_length"):
            with self.subTest(fact=key):
                self.assertIn(key, facts)
                self.assertEqual(facts[key]["checked"], "2026-10-15")
                self.assertIn("source", facts[key])
        self.assertEqual(facts["hashtag_cap"]["value"], 5)
        self.assertEqual(facts["hashtag_cap"]["since"], "2025-12-18")
        self.assertEqual(facts["caption_limit"]["value"], 2200)
        self.assertEqual(facts["carousel"]["max_items"], 20)
        self.assertEqual(facts["reel_max_length"]["value"], 180)

    def test_repo_file_is_found(self):
        caption = load_caption()
        self.assertEqual(os.path.realpath(caption.find_platform()), os.path.realpath(PLATFORM))
        self.assertEqual((caption.LIMIT, caption.TRUNCATE, caption.HASHTAG_LIMIT), (2200, 125, 5))

    def test_values_come_from_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "platform.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"facts": {"hashtag_cap": {"value": 3},
                                     "caption_limit": {"value": 100}}}, fh)
            caption = load_caption(path)
        self.assertEqual(caption.HASHTAG_LIMIT, 3)
        self.assertEqual(caption.LIMIT, 100)
        self.assertEqual(caption.TRUNCATE, 125)          # missing fact: fallback
        a = caption.analyse("A line with 4 tags.\n\n#one #two #three #four")
        tags = next(c for c in a["checks"] if c["check"] == "HASHTAGS")
        self.assertEqual(tags["status"], "FAIL")
        self.assertIn("cap of 3", tags["detail"])
        a = caption.analyse("x" * 150)
        self.assertEqual(next(c for c in a["checks"] if c["check"] == "LENGTH")["status"], "FAIL")

    def test_fallback_when_file_is_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "platform.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("not json")
            caption = load_caption(path)
        self.assertEqual((caption.LIMIT, caption.TRUNCATE, caption.HASHTAG_LIMIT), (2200, 125, 5))

    def test_unicode_hashtags_count(self):
        caption = load_caption()
        a = caption.analyse("मैंने $18,000 गंवा दिए।\n\n#भारत #फ्रीलांस #contracts")
        self.assertEqual(a["hashtags"], ["#भारत", "#फ्रीलांस", "#contracts"])


if __name__ == "__main__":
    unittest.main()

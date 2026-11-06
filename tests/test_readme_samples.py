"""The sample outputs printed in README.md still reproduce."""

import unittest

from _load import load

hookscore = load("ig-reel/hookscore.py")
beats = load("ig-reel/beats.py")

README_HOOKS = [
    ("Nobody tells you that your first 30 reels are supposed to flop", 85.6, "STRONG", "SPECIFICITY"),
    ("I lost $18,000 because of one missing contract.", 81.4, "STRONG", "ADDRESS"),
    ("Stop scrolling if you want to grow on Instagram in 2026 🔥", 54.4, "OK", "STAKES"),
    ("Hey guys, today I wanted to talk about content strategy", 9.6, "WEAK", "FRONTLOAD"),
    # The swipe-file sample, rounded there to whole numbers.
    ("steal this four line follow up it took me two years", 57.2, "OK", None),
    ("in this video I am going to show you my morning routine", 13.2, "WEAK", None),
]

# Beat 2's exact words are not in the README; this one has its length (40
# words, one sentence), which is all the timings depend on.
README_SCRIPT = """I lost $18,000 because of one missing contract.
Here is the exact clause I now put in every single contract I send, and it has saved me twice this year already, once with a client who went quiet for a month and once with one who changed scope.
Section 4. Payment on delivery, not on approval.
Approval is a feeling. Delivery is a date.
That one word change is worth $18,000 to me.
"""


class ReadmeHooks(unittest.TestCase):
    def test_scores(self):
        for text, score, verdict, weakest in README_HOOKS:
            with self.subTest(text=text):
                results, overall, v, flags = hookscore.run(text)
                self.assertEqual(round(overall, 1), score)
                self.assertEqual(v, verdict)
                if weakest:
                    self.assertEqual(hookscore.weakest_check(results), weakest)

    def test_dealbreakers(self):
        _, _, _, flags = hookscore.run("Hey guys, today I wanted to talk about content strategy")
        self.assertTrue(any(f.startswith("Greeting.") for f in flags))
        _, _, _, flags = hookscore.run("Stop scrolling if you want to grow on Instagram in 2026 🔥")
        self.assertTrue(any("stop scrolling" in f for f in flags))


class ReadmeBeatSheet(unittest.TestCase):
    def test_beat_sheet(self):
        a = beats.analyse(README_SCRIPT, target=30)
        self.assertEqual(a["total_words"], 73)
        self.assertEqual(round(a["total_seconds"], 1), 26.6)
        got = [(beats.tc(b["start"]), f"{b['dur']:.1f}", b["label"]) for b in a["beats"]]
        self.assertEqual(got, [("0:00.0", "2.9", "HOOK"), ("0:02.9", "14.6", "MID"),
                               ("0:17.4", "2.9", ""), ("0:20.4", "2.9", ""),
                               ("0:23.3", "3.3", "CTA")])
        notes = " ".join(a["notes"])
        self.assertIn("Beat(s) 2 run past 4s", notes)
        self.assertIn('Loops: the last beat repeats "$18,000"', notes)
        self.assertIn("3.5s under target. Either add 9 words", notes)


if __name__ == "__main__":
    unittest.main()

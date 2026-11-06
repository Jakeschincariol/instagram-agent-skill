"""Deleting a phrase must not leave stray punctuation behind."""

import unittest

from _load import load, lexicon

humanize = load("ig-human/humanize.py")
detect = load("ig-human/detect.py")
LEX = lexicon()


def clean(text):
    return humanize.humanize(text, LEX)[0].strip()


class OrphanPunctuation(unittest.TestCase):
    def test_reported_cases(self):
        self.assertEqual(clean("This changed everything for me. Follow for more!"),
                         "This worked for me.")
        self.assertIn(clean("Save this — tag someone who needs this 👇"),
                      ("Save this 👇", "Save this. 👇"))

    def test_regressions(self):
        cases = {
            "Follow for more! Next one drops Friday.": "Next one drops Friday.",
            "Great results, follow for more!": "Great results!",
            "Save this — tag someone who needs this. Then go.": "Save this. Then go.",
            "Here's the thing: you need a contract.": "You need a contract.",
            "It works, at the end of the day, for me.": "It works, for me.",
            "We shipped it on Monday. What are your thoughts?": "We shipped it on Monday.",
            "Line one.\nFollow for more\nLine two.": "Line one.\n\nLine two.",
        }
        for src, want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(clean(src), want)

    def test_no_junk_after_any_deletion(self):
        deletable = [e["find"] for e in LEX["phrases"] + LEX["words"] if not e["replace"]]
        for phrase in deletable:
            cap = phrase[0].upper() + phrase[1:]
            for src in (f"We shipped it on Monday. {cap}!",
                        f"{cap}. We shipped it on Monday.",
                        f"We shipped it — {phrase} 👇",
                        f"We shipped it, {phrase}."):
                with self.subTest(src=src):
                    out = clean(src)
                    for junk in (".!", ",!", ".,", ",.", " ,", " .", ", 👇", "?,"):
                        self.assertNotIn(junk, out)
                    self.assertFalse(out[:1] in ",.!?;:", out)

    def test_human_punctuation_left_alone(self):
        for src in ("Wait. Really?!", "Love this, 🔥", "So... it worked.", "Done!! Shipped."):
            with self.subTest(src=src):
                self.assertEqual(clean(src), src)

    def test_punctuation_ended_phrase_is_found(self):
        pattern = humanize.phrase_pattern("what are your thoughts?")
        self.assertTrue(pattern.search("Nice one. What are your thoughts?"))
        self.assertTrue(detect.phrase_pattern("follow for more").search("Follow for more!"))
        self.assertFalse(detect.phrase_pattern("delve").search("delved"))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""FINGERPRINT must count every space class slop.json declares.

ig-human/SKILL.md promises the detector reads all 18 invisible character
classes that `humanize.py` strips. The FINGERPRINT check listed three of the
six space classes by hand, so U+2002 EN SPACE, U+2003 EM SPACE and U+2007
FIGURE SPACE - the three a PDF or a layout tool emits where an ordinary space
belongs - were removed by `humanize.py` and reported as "0 hard space" by
`detect.py` on the exact same file.

Uses stdlib unittest only; the pack ships no dependencies.

    python3 -m unittest discover -s tests
"""

import json
import os
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
IG_HUMAN = os.path.join(ROOT, "skills", "ig-human")
sys.path.insert(0, IG_HUMAN)

import detect  # noqa: E402

LEX_PATH = os.path.join(IG_HUMAN, "slop.json")


def sample_char(spec):
    """'U+00A0' -> that character; a range -> its first character."""
    return chr(int(spec.split("-")[0][2:], 16))


class FingerprintCoversEveryDeclaredClass(unittest.TestCase):
    """Every assertion goes through detect.run(), the public entry point."""

    def setUp(self):
        with open(LEX_PATH, encoding="utf-8") as fh:
            self.lex = json.load(fh)

    def fingerprint(self, text):
        results, _, _ = detect.run(text, self.lex)
        score, detail = results["FINGERPRINT"]
        return score, detail

    def test_every_space_class_in_the_lexicon_is_counted(self):
        declared = [e for e in self.lex["invisible"] if e["action"] == "space"]
        self.assertEqual(len(declared), 6, "slop.json space classes")
        missed = []
        for entry in declared:
            _, detail = self.fingerprint("A draft sentence here." + sample_char(entry["cp"]))
            if "0 hard space" in detail:
                missed.append(f"{entry['cp']} {entry['name']}")
        self.assertEqual(missed, [], "not counted by FINGERPRINT: " + ", ".join(missed))

    def test_a_caption_pasted_from_a_pdf_scores_lower_than_the_same_text_typed(self):
        typed = "I lost $18,000 on one clause in 2024 and signed it anyway."
        # What a layout tool emits instead of U+0020.
        pasted = typed.replace("18,000", "18,000\u2007").replace("one", "one\u2003")
        typed_score, _ = self.fingerprint(typed)
        pasted_score, pasted_detail = self.fingerprint(pasted)
        self.assertLess(pasted_score, typed_score,
                        "invisible spaces did not lower FINGERPRINT (" + pasted_detail + ")")

    def test_detect_sees_the_artefacts_humanize_removes(self):
        """The two tools read one lexicon; they must not disagree on it."""
        draft = "We quoted 11 projects\u2003and lost four\u2007on price."
        _, detail = self.fingerprint(draft)
        self.assertNotIn("0 hard space", detail,
                         "detect.py saw no artefact where humanize.py removes two")

    def test_ordinary_spaces_are_not_a_fingerprint(self):
        score, detail = self.fingerprint("I lost $18,000 on one clause in 2024 and signed it anyway.")
        self.assertEqual(score, 100.0, detail)


if __name__ == "__main__":
    unittest.main()

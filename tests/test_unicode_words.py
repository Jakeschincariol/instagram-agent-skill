"""Word counting works in any script, and the English results do not move."""

import unittest

from _load import load

hookscore = load("ig-reel/hookscore.py")
beats = load("ig-reel/beats.py")
swipe = load("ig-viral/swipe.py")
detect = load("ig-human/detect.py")

EN = "I lost $18,000 because of one missing contract."
ES = "Perdí $18,000 por culpa de un contrato que faltaba."
HI = "एक गायब कॉन्ट्रैक्ट की वजह से मैंने $18,000 गंवा दिए।"
UR = "ایک غائب کنٹریکٹ کی وجہ سے میں نے $18,000 گنوا دیے۔"
HI_ALT = "मैंने एक गायब कॉन्ट्रैक्ट की वजह से $18,000 खो दिए।"
HINGLISH = "Ek missing contract ki wajah se maine $18,000 gawa diye."
RU = "Я потерял $18,000 из-за одного пропавшего контракта."

HINDI_SCRIPT = """एक गायब कॉन्ट्रैक्ट की वजह से मैंने $18,000 गंवा दिए।
अब मैं हर कॉन्ट्रैक्ट में यह एक लाइन जोड़ता हूँ: भुगतान डिलीवरी पर, अप्रूवल पर नहीं।
उस एक लाइन की कीमत मेरे लिए $18,000 है।
"""


class WordCounting(unittest.TestCase):
    def test_counts_per_script(self):
        cases = {
            HI: 10,
            UR: 11,
            HINGLISH: 10,
            RU: 7,
            ES: 9,
            "El año pasado está bien": 5,
            "Café au lait": 3,          # decomposed accent stays in the word
        }
        for text, n in cases.items():
            with self.subTest(text=text):
                self.assertEqual(len(hookscore.words(text)), n)
                self.assertEqual(len(beats.words(text)), n)
                self.assertEqual(len(swipe.WORD_RE.findall(
                    text.replace("18,000", "18000"))), n)

    def test_vowel_signs_stay_inside_words(self):
        self.assertEqual(hookscore.words("मैंने कॉन्ट्रैक्ट"), ["मैंने", "कॉन्ट्रैक्ट"])
        self.assertEqual(detect.words("मैंने कॉन्ट्रैक्ट"), ["मैंने", "कॉन्ट्रैक्ट"])
        self.assertEqual(hookscore.words("میں نے"), ["میں", "نے"])

    def test_english_tokens_unchanged(self):
        self.assertEqual(hookscore.words("well-known rep’s 50% $1,200 don't"),
                         ["well-known", "rep’s", "50%", "$1200", "don't"])
        self.assertEqual(detect.words("It's 5 o'clock, Jake."), ["It's", "o'clock", "Jake"])


class HindiBeatSheet(unittest.TestCase):
    def test_hindi_script_has_words_and_time(self):
        a = beats.analyse(HINDI_SCRIPT)
        self.assertEqual(len(a["beats"]), 3)
        self.assertGreaterEqual(a["total_words"], 30)
        self.assertGreater(a["total_seconds"], 10)
        self.assertTrue(all(b["words"] > 0 for b in a["beats"]))

    def test_caseless_beats_are_unknown_not_abstract(self):
        a = beats.analyse("भुगतान डिलीवरी पर होगा\nअप्रूवल एक एहसास है\nडिलीवरी एक तारीख है\n")
        self.assertTrue(all(b["concrete"] is None for b in a["beats"]))
        self.assertFalse(any("nothing concrete" in n for n in a["notes"]))

    def test_danda_splits_long_lines(self):
        line = "।".join(["यह एक बहुत लंबी लाइन है जिसमें कई शब्द हैं"] * 4) + "।"
        a = beats.analyse(line)
        self.assertGreater(len(a["beats"]), 1)


class TranslatedHookScores(unittest.TestCase):
    def score(self, text):
        _, overall, verdict, _ = hookscore.run(text)
        return overall, verdict

    def test_translations_land_near_the_original(self):
        en, _ = self.score(EN)
        es, _ = self.score(ES)
        for text in (HI, UR, HI_ALT):
            with self.subTest(text=text):
                s, verdict = self.score(text)
                self.assertNotEqual(verdict, "WEAK")
                self.assertTrue(abs(s - en) <= 15 or abs(s - es) <= 15,
                                f"{s:.1f} vs en {en:.1f} / es {es:.1f}")

    def test_length_is_not_the_problem(self):
        for text in (HI, UR, HI_ALT, RU):
            with self.subTest(text=text):
                results, _, _, _ = hookscore.run(text)
                self.assertEqual(results["LENGTH"][0], 100.0)

    def test_english_only_checks_go_neutral(self):
        results, _, _, _ = hookscore.run(HI)
        self.assertTrue(results["ADDRESS"][1].startswith("n/a"))
        self.assertEqual(results["ADDRESS"][0], hookscore.NA)
        self.assertNotIn(hookscore.weakest_check(results), ("ADDRESS", "FRONTLOAD"))

    def test_caseless_hook_without_digits_does_not_crash(self):
        results, overall, verdict, flags = hookscore.run("भुगतान डिलीवरी पर होगा, अप्रूवल पर नहीं")
        self.assertTrue(results["SPECIFICITY"][1].startswith("n/a"))
        self.assertGreaterEqual(overall, 0)

    def test_detect_is_neutral_on_hindi(self):
        text = ("पिछले साल मैंने एक क्लाइंट के साथ काम किया और कॉन्ट्रैक्ट में एक लाइन नहीं थी। "
                "नतीजा यह हुआ कि मेरे $18,000 डूब गए। अब मैं हर कॉन्ट्रैक्ट में लिखता हूँ कि "
                "भुगतान डिलीवरी पर होगा, अप्रूवल पर नहीं। अप्रूवल एक एहसास है। डिलीवरी एक "
                "तारीख है। तीन महीने में दो बार इस एक लाइन ने मुझे बचाया।")
        from _load import lexicon
        results, overall, verdict = detect.run(text, lexicon())
        self.assertNotEqual(results["BURSTINESS"][1], "too short to judge")
        self.assertTrue(results["VOICE"][1].startswith("n/a"))
        self.assertTrue(results["SLOP DENSITY"][1].startswith("n/a"))
        self.assertNotEqual(verdict, "FLAGGED")


if __name__ == "__main__":
    unittest.main()

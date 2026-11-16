#!/usr/bin/env python3
"""
hookscore.py - score the first line of a Reel on the five things strong hooks
have in common, and rank a batch of them against each other.

What this is:  five local heuristics, computed on your machine from the text
alone. They measure properties that hooks which hold attention tend to share -
a length you can say in under three seconds, a concrete marker, something at stake,
the payload at the front rather than the back, and a viewer to aim it at.

What this is NOT:  a view predictor. It was tested against 74 real short-form
hooks, transcribed from the first three seconds of the top eight and bottom
eight performers on five channels. Separating a real hook from a deliberately
bad one it does well: AUC 0.83, and 9 of 10 written-to-be-bad hooks scored
below the real median. Separating a good creator's hits from that same
creator's misses it barely does at all: AUC 0.56, where 0.50 is a coin flip.

So use it for what it measured well. It catches greetings, preambles, hooks
with nothing concrete in them and hooks that take five seconds to say. It will
not tell you which of two decent hooks will travel, and nothing that reads text
can, because that is decided by your face, your edit, your audio and who
Instagram shows it to. Trust the retention graph over this script.

Each check returns 0 to 100. Higher is better.

Usage
  python3 hookscore.py hooks.txt              # one hook per line, ranked
  python3 hookscore.py --hook "I lost $18,000 on one missing contract."
  pbpaste | python3 hookscore.py -
  python3 hookscore.py hooks.txt --json

Exit status
  0  the best hook scored 70 or more
  1  the best hook scored under 70. This is a verdict, not an error: the
     ranking was printed and is valid, there is just no strong hook in it
  2  nothing to score (empty input)
"""

import argparse
import json
import re
import statistics
import sys

# --- Devanagari support ------------------------------------------------------
# The same block is in hookscore.py, beats.py, detect.py, humanize.py,
# caption.py and swipe.py, so each script still works when it is copied on its
# own; tests/hindi.py fails if the six copies drift apart. English text has no
# Devanagari in it, so nothing in this block changes what English input gives.
import unicodedata as _ud  # noqa: E402

DEVA = "\u0900-\u0963\u0966-\u097f\ua8e0-\ua8ff"    # letters, signs, digits; not the danda
DANDA = "\u0964\u0965"                               # । and ॥ end a sentence, like "."
# A joiner or a hyphen inside a word keeps it one word: सोच-समझकर is one word,
# the way "fast-paced" is one word in English.
DEVA_WORD_RE = re.compile("[" + DEVA + "]+(?:[\u200c\u200d-][" + DEVA + "]+)*")
NOT_PROSE_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+|[#@]\S+")
CALIBRATION = ("uncalibrated: the thresholds were set on English text, so read "
               "this as a rough guide for Hindi")


def lang_of(text):
    """'en' if there is no Devanagari word, 'hi' if at least four words in five
    are Devanagari, otherwise 'mixed'. Links, hashtags and @handles are not
    counted. Hindi typed in Latin letters ("aap kaise ho") reads as 'en'."""
    body = NOT_PROSE_RE.sub(" ", text)
    hi = len(DEVA_WORD_RE.findall(body))
    if not hi:
        return "en"
    en = len(re.findall(r"[A-Za-z]+", body))
    return "hi" if hi >= 4 * en else "mixed"


def deva_fold(text):
    """One spelling for comparing Hindi, used only for matching, never for
    output. Each rule joins two spellings of the same word:
      nukta dropped            ज़रूरी = जरूरी, ग़लत = गलत
      candrabindu = anusvara   पाँच = पांच
      visarga dropped          निःसंदेह = निसंदेह, दुःख = दुख
      त्त्व = त्व                महत्त्वपूर्ण = महत्वपूर्ण
      -ये / -यी endings        गये = गए, लिये = लिए, नयी = नई (the word ये is kept)
      यह = ये                  यह कहना = ये कहना
      hyphen in a compound     भाग-दौड़ = भागदौड़
      zero-width joiners       dropped
    Text without Devanagari comes back unchanged."""
    if not re.search("[" + DEVA + "]", text):
        return text
    t = _ud.normalize("NFC", text)
    t = t.replace("\u093c", "").replace("\u0901", "\u0902").replace("\u0903", "")
    t = t.replace("\u0924\u094d\u0924\u094d\u0935", "\u0924\u094d\u0935")
    t = re.sub("[\u200c\u200d]", "", t)
    t = re.sub("(?<=[" + DEVA + "])-(?=[" + DEVA + "])", "", t)
    t = re.sub("(?<=[" + DEVA + "])\u092f\u0947(?![" + DEVA + "])", "\u090f", t)
    t = re.sub("(?<=[" + DEVA + "])\u092f\u0940(?![" + DEVA + "])", "\u0908", t)
    return re.sub("(?<![" + DEVA + "])\u092f\u0939(?![" + DEVA + "])", "\u092f\u0947", t)


def deva_edges(body):
    """A regex that matches `body` only as whole words. \\b cannot do this for
    Hindi: Python counts vowel signs as non-word characters, so \\b fires in
    the middle of रुकिए."""
    edge = r"[\w" + DEVA + "]"
    return "(?<!" + edge + ")(?:" + body + ")(?!" + edge + ")"


def deva_re(body):
    """Compile a Hindi pattern. Match it against deva_fold(text)."""
    return re.compile(deva_edges(deva_fold(body)), re.IGNORECASE)


def danda_text(text):
    """A '|' typed straight after a Hindi word is a danda: many phone keyboards
    have no ।. Only used for finding sentence ends, never written back."""
    return re.sub("(?<=[" + DEVA + r"])[ \t]*\|", "\u0964", text)


def _deva_set(*groups):
    return {deva_fold(w) for g in groups for w in g.split()}


# Spoken numbers and money words, the Hindi half of SPOKEN_NUMBERS and
# MONEY_WORDS. एक (one) and पहला (first) are left out for the same reason
# "one" is: far more often filler than a quantity.
HI_SPOKEN_NUMBERS = _deva_set(
    "दो तीन चार पाँच पांच छह छः सात आठ नौ दस ग्यारह बारह पंद्रह बीस पच्चीस तीस",
    "चालीस पचास साठ सत्तर अस्सी नब्बे सौ हज़ार हजार लाख करोड़ अरब दर्जन",
    "आधा आधी आधे डेढ़ ढाई साढ़े सवा पौने दोगुना दुगना तिगुना")
HI_MONEY_WORDS = _deva_set(
    "रुपये रुपए रुपया रुपयों पैसे पैसा किराया किराए सैलरी तनख़्वाह वेतन मुनाफ़ा",
    "ब्याज कीमत क़ीमत दाम बजट लोन ईएमआई प्रतिशत फ़ीसदी")
# The viewer, and the speaker. Same jobs as "you" and "I/we" in English.
HI_YOU = _deva_set("आप आपका आपकी आपके आपको आपने आपसे तुम तुम्हें तुम्हारा तुम्हारी",
                   "तुम्हारे तू तेरा तेरी तेरे तुझे")
HI_ME = _deva_set("मैं मैंने मेरा मेरी मेरे मुझे मुझसे हम हमने हमारा हमारी हमारे हमें")
# दो is two, and also "give" (पैसे दो, बता दो). As a verb it closes the clause
# or follows another verb, so it is not counted there.
_HI_DO_VERB_BEFORE = _deva_set("दे कर बता लिख भेज छोड़ रख ले दिखा समझा सुना")
_HI_DO_VERB_AFTER = _deva_set("और फिर ना तो जी यार भाई")


def hi_number_hits(tokens):
    """Positions of the Hindi number and money words in a list of
    deva_fold()ed tokens. Positions, so a caller can show the writer's own
    spelling rather than the folded one."""
    hits = []
    for i, t in enumerate(tokens):
        if t in HI_SPOKEN_NUMBERS or t in HI_MONEY_WORDS:
            if t == "दो" and (i == len(tokens) - 1 or (i and tokens[i - 1] in _HI_DO_VERB_BEFORE)
                              or tokens[i + 1] in _HI_DO_VERB_AFTER):
                continue
            hits.append(i)
    return hits
# --- end of Devanagari support -----------------------------------------------


WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+|" + DEVA_WORD_RE.pattern)
NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"                       # money, whole
    r"|\b\d[\d,]*(?:\.\d+)?\s?"                      # a figure, with or
    r"(?:%|k\b|x\b|hrs?\b|hours?\b|mins?\b|minutes?\b"  # without a unit
    r"|days?\b|weeks?\b|months?\b|years?\b)?",
    re.IGNORECASE)
PROPER_RE = re.compile(r"(?<!^)\b[A-Z][a-z]{2,}\b")
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

# Spoken hooks say their numbers out loud. "Zero dollars" and "twenty grand"
# are as concrete as "$0" and "$20,000", and counting only digits missed them.
# "one" and "first" are deliberately absent: they are filler far more often
# than they are a quantity.
SPOKEN_NUMBERS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
    "billion", "dozen", "half", "twice", "triple",
}
MONEY_WORDS = {
    "dollars", "dollar", "bucks", "grand", "percent", "cents",
    "millionaire", "billionaire", "revenue", "profit", "salary", "rent",
}

# Words that put something on the line. A hook with none of these is a
# statement; a hook with one is a reason to keep watching.
STAKES = {
    "stop", "never", "wrong", "mistake", "mistakes", "lost", "lose", "losing",
    "cost", "costs", "broke", "broken", "failed", "failure", "fail", "nobody",
    "no", "not", "don't", "dont", "doesn't", "didn't", "can't", "won't",
    "quit", "quitting", "fired", "deleted", "delete", "killed", "kills", "kill",
    "replaced", "replaces", "cut", "beat", "free", "paid", "charged", "hired",
    "saved", "first",
    "banned", "illegal", "worst", "hate", "hated", "wasted", "waste", "scam",
    "lie", "lied", "lying", "truth", "secret", "hidden", "stole", "stolen",
    "before", "until", "instead", "but", "except", "unless", "problem",
    "risk", "danger", "warning", "regret", "wish", "should", "shouldn't",
    "still", "already", "only", "without", "versus", "vs", "actually",
}

# Openers that spend the first second saying nothing.
WEAK_OPENERS = [
    "so", "ok", "okay", "hey", "hi", "hello", "guys", "yo", "alright",
    "welcome", "today", "basically", "honestly", "look", "listen", "um",
    "just", "let", "lets", "let's", "i wanted", "i want", "one of",
    "have you", "did you", "do you", "are you", "in this", "in today",
    "the thing", "a lot", "there is", "there are", "this is", "it is",
    "as a", "when it", "if you've", "you know",
]

# Imperatives that earn the front position.
IMPERATIVES = {
    "stop", "steal", "copy", "delete", "try", "watch", "read", "save",
    "use", "build", "make", "write", "send", "take", "start", "quit",
    "never", "always", "don't", "dont", "do", "put", "run", "check",
}

# Hindi counterparts of STAKES, WEAK_OPENERS and IMPERATIVES. Compared after
# deva_fold, so a word counts with or without its nukta or candrabindu. These
# lists are a first draft for a native speaker to review, and the thresholds
# below were set on English hooks: Hindi scores are labelled uncalibrated.
HI_STAKES = _deva_set(
    "नहीं नही मत गलती ग़लती गलतियाँ गलत नुकसान नुक़सान घाटा रुकिए रुको रुकें सावधान",
    "धोखा धोखाधड़ी फ्रॉड ठगी खतरा ख़तरा जोखिम बर्बाद गँवाए गँवा खोया खो डूब डूबे",
    "फँस फँसे पछतावा पछताएंगे पहले बिना सिर्फ़ केवल लेकिन मगर सच सच्चाई छुपा छिपा",
    "रहस्य अवैध गैरकानूनी बचाए बचा बचत मुफ़्त फ्री वरना कभी समस्या दिक्कत चेतावनी")
# राज़ (secret) is left out on purpose: without its nukta it is राज, a name.
HI_WEAK_OPENERS = [deva_fold(w).split() for w in (
    "नमस्ते", "नमस्कार", "हेलो", "हैलो", "हाय", "वेलकम", "दोस्तों", "दोस्तो", "तो",
    "आज", "बस", "देखिए", "देखो", "सुनिए", "सुनो", "चलिए", "अच्छा", "क्या आप",
    "आप सभी", "जैसा कि", "इस वीडियो", "इस रील")]
# Hindi puts the verb last, so a Hindi imperative counts wherever it stands.
# Polite forms end in -िए / -इए (रुकिए, बताइए). Words with that ending that are
# not commands: लिए/लिये, किए/किये, दिए/दिये (spelling is folded), चाहिए, इसलिए.
# The -ें forms are listed verb by verb, because -ें also ends plural nouns
# (बातें, चीज़ें) and में. A -ना verb is a command only after मत, न or ज़रूर
# (मत करना, ज़रूर देखना); on its own it is usually a noun (रोज़ उठना आसान नहीं).
HI_IMPERATIVES = _deva_set("मत रुको रुकें बचो बचें करो करें लिखो लिखें भेजो भेजें छोड़ो छोड़ें",
                           "पढ़ें देखें खरीदें जानें रखें भरें लें दें सोचें समझें पूछें चुनें जाँचें माँगें",
                           "बताएं बताएँ पढ़ो देखो जानो रखो पूछो")
HI_IMPERATIVE_ENDS = tuple(deva_fold(e) for e in ("िए", "िये", "इए", "इये", "िएगा", "इएगा"))
HI_NOT_IMPERATIVE = _deva_set("लिए किए दिए पिए जिए सिए चाहिए इसलिए किसलिए जिसलिए उसलिए")
HI_NA_COMMAND_AFTER = _deva_set("मत न ना ज़रूर")
HI_DEALBREAKERS = [
    (deva_re(r"^\s*(?:स्क्रॉल|scroll) (?:मत|ना) (?:करो|करें|कीजिए|करिए)"
             r"|^\s*(?:स्क्रॉल|scroll) करना (?:बंद|रोकिए|रोको)"),
     "Opens with \"stop scrolling\". Asking for attention proves you have not earned it."),
    (deva_re(r"(?:आज के |आज की )?(?:इस|आज के|आज की) (?:वीडियो|विडियो|रील) में"
             r"|मैं (?:आपको|आप को) (?:बताऊँगा|बताऊँगी|बताने वाला|बताने वाली|दिखाऊँगा|दिखाऊँगी|दिखाने वाला)"),
     "Video preamble. Delete it and open on the payoff."),
    (deva_re(r"^\s*(?:नमस्ते|नमस्कार|प्रणाम|हेलो|हैलो|हाय|वेलकम|जय जोहार|राम राम)"),
     "Greeting. Nobody came to the feed to be greeted."),
]


def hi_command(tokens):
    """(start, end) positions of the first Hindi command in a list of folded
    tokens, or None."""
    for i, t in enumerate(tokens):
        if t in HI_IMPERATIVES or (t.endswith(HI_IMPERATIVE_ENDS) and t not in HI_NOT_IMPERATIVE):
            return i, i
        if len(t) > 2 and t.endswith("ना") and i and tokens[i - 1] in HI_NA_COMMAND_AFTER:
            return i - 1, i
    return None


DEALBREAKERS = [
    (re.compile(r"(?i)^\s*(?:stop scrolling|don'?t scroll)"),
     "Opens with \"stop scrolling\". Asking for attention proves you have not earned it."),
    (re.compile(r"(?i)\b(?:in (?:this|today'?s) (?:video|reel)|i'?m going to show you|i'?ll show you how)\b"),
     "Video preamble. Delete it and open on the payoff."),
    (re.compile(r"(?i)^\s*(?:hey |hi |what'?s up |welcome )"),
     "Greeting. Nobody came to the feed to be greeted."),
    (HASHTAG_RE,
     "Hashtag in the hook. Hashtags belong at the bottom of the caption, if anywhere."),
    (EMOJI_RE,
     "Emoji in the hook. On-screen text at hook size has room for words or for an emoji, not both."),
]


def clamp(n):
    return max(0.0, min(100.0, n))


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def check_length(text):
    """A hook has to land before the thumb moves. Roughly two seconds."""
    w = words(text)
    n = len(w)
    secs = n / (2.75 if lang_of(text) == "en" else 2.5)   # ~165 wpm spoken, 150 for Hindi
    chars = len(text.strip())
    if 5 <= n <= 12:
        score = 100.0
    elif n < 5:
        score = clamp(100 - (5 - n) * 20)
    else:
        score = clamp(100 - (n - 12) * 11)
    if chars > 60:                       # two lines of big on-screen text
        score -= 12
    return clamp(score), f"{n} words, {chars} chars, ~{secs:.1f}s spoken (want 5-12 words)"


def check_specificity(text):
    """One concrete thing beats three abstract ones."""
    nums = [n.strip() for n in NUMBER_RE.findall(text) if n.strip()]
    propers = set(PROPER_RE.findall(text))
    raw = [w.lower().strip("'’") for w in words(text)]
    low = [deva_fold(w) for w in raw]          # matched folded, shown as written
    spoken = [w for w in low if w in SPOKEN_NUMBERS or w in MONEY_WORDS] + [raw[i] for i in hi_number_hits(low)]
    hits = len(nums) + len(propers) + len(spoken)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join(nums[:2] + sorted(propers)[:2] + spoken[:2])
    return score, (f"{hits} concrete marker(s)" + (f": {found}" if found else
                   " - no number, no name, nothing checkable"))


def check_stakes(text):
    """Tension, cost, negation. Something the viewer might lose."""
    raw = [x.lower().strip("'’") for x in words(text)]
    w = [deva_fold(x) for x in raw]
    hits = [raw[i] for i, x in enumerate(w) if x in STAKES or x in HI_STAKES]
    markers = sorted(set(hits))
    if re.search(r"\$\s?\d", text) or (lang_of(text) != "en" and re.search(r"₹\s?\d", text)):
        markers.append("a price")
    n = len(markers)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detail = f"{n} tension marker(s)" + (f": {', '.join(markers[:4])}" if markers else
                                         " - nothing is at stake in this line")
    return clamp(score), detail


def check_frontload(text):
    """The interesting word cannot be in position nine."""
    w = words(text)
    if not w:
        return 0.0, "empty"
    low = [deva_fold(x.lower().strip("'’")) for x in w]
    opener = " ".join(low[:2])
    penalty = 0
    hit_opener = None
    for weak in WEAK_OPENERS:
        if opener.startswith(weak) or low[0] == weak:
            penalty, hit_opener = 30, weak
            break
    if hit_opener is None:
        for weak in HI_WEAK_OPENERS:        # whole words: तो is weak, तोड़ is not
            if low[:len(weak)] == weak:
                penalty, hit_opener = 30, " ".join(x.lower() for x in w[:len(weak)])
                break
    payload = None
    for i, token in enumerate(low):
        if (token in STAKES or token in SPOKEN_NUMBERS or token in MONEY_WORDS
                or token in HI_STAKES or token in HI_SPOKEN_NUMBERS or token in HI_MONEY_WORDS
                or NUMBER_RE.match(w[i]) or (i and PROPER_RE.match(w[i]))):
            payload = i
            break
    if payload is None:
        base = 30.0
        where = "no payload word anywhere in the line"
    elif payload <= 3:
        base = 100.0
        where = f"payload at word {payload + 1}"
    elif payload <= 6:
        base = 70.0
        where = f"payload at word {payload + 1}, could move forward"
    else:
        base = 40.0
        where = f"payload at word {payload + 1}, too late"
    detail = where + (f"; weak opener \"{hit_opener}\"" if hit_opener else "")
    return clamp(base - penalty), detail


def check_address(text):
    """Aimed at one viewer, or floating in the air."""
    low = text.lower()
    raw = [x.lower().strip("'’") for x in words(text)]
    w = [deva_fold(x) for x in raw]
    if re.search(r"\b(you|your|you're|youre|yourself)\b", low):
        return 100.0, "speaks to the viewer"
    if any(x in HI_YOU for x in w):
        return 100.0, "speaks to the viewer"
    if w and w[0] in IMPERATIVES:
        return 90.0, f"imperative opener (\"{w[0]}\")"
    hi_cmd = hi_command(w)
    if hi_cmd:
        return 90.0, f"imperative (\"{' '.join(raw[hi_cmd[0]:hi_cmd[1] + 1])}\")"
    if re.search(r"\b(i|my|me|we|our)\b", low):
        return 70.0, "first person, no viewer named"
    if any(x in HI_ME for x in w):
        return 70.0, "first person, no viewer named"
    return 35.0, "third person, nobody in the room"


CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]


def run(text):
    results = {
        "LENGTH": check_length(text),
        "SPECIFICITY": check_specificity(text),
        "STAKES": check_stakes(text),
        "FRONTLOAD": check_frontload(text),
        "ADDRESS": check_address(text),
    }
    flags = [msg for pattern, msg in DEALBREAKERS if pattern.search(text)]
    if lang_of(text) != "en":
        folded = deva_fold(text)
        flags += [msg for pattern, msg in HI_DEALBREAKERS
                  if pattern.search(folded) and msg not in flags]
    scores = [results[c][0] for c in CHECKS]
    # The weakest property caps the hook, same logic as detect.py: one bad
    # property is enough for the thumb to keep moving.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render_one(text, results, overall, verdict, flags, out=sys.stdout):
    print("\nHOOK SCORE", file=out)
    print("=" * 62, file=out)
    print(f"  \"{text.strip()}\"\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HOOK SCORE':<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    for f in flags:
        print(f"\n  DEALBREAKER  {f}", file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  Weakest property: {weakest}. Fix that one and re-run.", file=out)
    if lang_of(text) != "en":
        print(f"\n  Language: {lang_of(text)}. Score is {CALIBRATION}.", file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout):
    print("\nHOOK RANKING\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        tag = f"  [{r['lang']}]" if "lang" in r else ""
        print(f"{mark} {r['score']:5.1f} {r['verdict']:<7} {hook}{tag}", file=out)
        print(f"        weakest: {r['weakest']} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        dealbreaker: {f}", file=out)
    if any("lang" in r for r in rows):
        print(f"\nLines marked [hi] or [mixed]: the score is {CALIBRATION}.", file=out)
    print("\nShoot the top one. If the top one is under 50, none of these are the hook.\n",
          file=out)


def main():
    ap = argparse.ArgumentParser(
        description="Score a Reel hook on five properties.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="exit status: 0 = best hook scored 70+, 1 = best hook under 70 (a verdict,\n"
               "not an error - the output is valid), 2 = nothing to score.")
    ap.add_argument("input", nargs="?", default="-", help="file with one hook per line, or -")
    ap.add_argument("--hook", help="score a single hook given on the command line")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.hook:
        lines = [args.hook]
    else:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        print("nothing to score", file=sys.stderr)
        sys.exit(2)

    payload = []
    for line in lines:
        results, overall, verdict, flags = run(line)
        entry = {
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": min(CHECKS, key=lambda c: results[c][0]),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
        }
        if lang_of(line) != "en":            # English output stays exactly as it was
            entry["lang"], entry["calibration"] = lang_of(line), CALIBRATION
        payload.append(entry)

    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False))
        return

    if len(payload) == 1:
        results, overall, verdict, flags = run(lines[0])
        render_one(lines[0], results, overall, verdict, flags)
    else:
        render_table(sorted(payload, key=lambda r: -r["score"]))

    sys.exit(0 if max(p["score"] for p in payload) >= 70 else 1)


if __name__ == "__main__":
    main()

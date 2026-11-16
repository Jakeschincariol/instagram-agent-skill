#!/usr/bin/env python3
"""
beats.py - turn a Reel script into a timed beat sheet before you record it.

Estimates how long each line takes to say, stacks them into timecodes, and
flags the four things that kill a Reel in the edit: a hook that runs past the
three-second mark, a beat long enough for the viewer to leave, a run of lines
with nothing concrete in them, and a total length that does not match what you
said you were making.

The timings are an estimate from word count at a words-per-minute rate. They
are close enough to plan an edit and not a substitute for recording it. Set
your own rate with --wpm once you have timed yourself reading a script out
loud: most people land between 150 and 200, and the default here is 165.

Usage
  python3 beats.py script.txt
  python3 beats.py script.txt --target 30
  python3 beats.py script.txt --wpm 185 --target 45
  pbpaste | python3 beats.py -
  python3 beats.py script.txt --json
"""

import argparse
import json
import os
import re
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


# One list of spoken numbers for the whole folder: hookscore.py owns it. Do not
# leave a __pycache__ behind in the skill folder just for importing it.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from hookscore import MONEY_WORDS, SPOKEN_NUMBERS  # noqa: E402
except ImportError:
    # beats.py copied on its own. Same lists as hookscore.py; keep them in sync.
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

WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+|" + DEVA_WORD_RE.pattern)
SENT_RE = re.compile(r"[^.!?" + DANDA + r"]+[.!?" + DANDA + r"]*")
CONCRETE_RE = re.compile(r"\$\s?\d|\b\d[\d,.]*\b|(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "for",
    "with", "that", "this", "it", "is", "are", "was", "were", "be", "been",
    "you", "your", "i", "my", "me", "we", "our", "they", "them", "he", "she",
    "so", "just", "not", "no", "do", "did", "does", "have", "has", "had",
    "will", "can", "at", "as", "by", "from", "out", "up", "off", "one", "all",
    # Filler that turns up in any two lines of speech. Sharing one of these is
    # not a loop: "about" in the hook and "think about it" at the end is not a
    # callback. Words that carry the idea (numbers, names, stakes) stay out.
    "about", "really", "very", "thing", "things", "something", "anything",
    "what", "how", "why", "when", "where", "who", "which", "there", "here",
    "then", "than", "into", "onto", "over", "more", "most", "some", "any",
    "get", "got", "going", "go", "make", "made", "like", "even", "also",
    "because", "would", "could", "should", "its", "it's", "i'm", "i'll",
    "i've", "that's", "these", "those", "think", "know", "want", "say", "said",
}

# Hindi function words: sharing है or में between the hook and the last line
# is not a loop, any more than sharing "the" is.
HI_STOPWORDS = _deva_set(
    "है हैं था थी थे हो का की के को में से पर और या तो भी ही ये यह वो वह एक कि",
    "मैं हम आप तुम इस उस जो क्या कैसे क्यों अब बस सब कुछ बहुत कर करें करना किया",
    "दिया लिए साथ वाला वाले वाली अपने अपना अपनी होता होती होते रहा रही रहे गया गई",
    "गए जब तब यहाँ वहाँ नहीं ना न")
WPM_EN, WPM_HI = 165, 150  # Hindi script read aloud runs slower per word

HOOK_WINDOW = 3.0        # seconds. Past this, the thumb has already decided.
MAX_BEAT = 4.0           # seconds on one idea with no change on screen.
ABSTRACT_RUN = 3         # beats in a row with nothing checkable in them.


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def pretty(token):
    """Put the thousands separator back for display."""
    return re.sub(r"(\d)(?=(\d{3})+$)", r"\1,", token)


def tc(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def split_beats(raw, wps):
    """One line is one beat, unless a line is too long to be one."""
    beats = []
    for line in [l.strip() for l in raw.splitlines()]:
        if not line:
            continue
        if len(words(line)) / wps <= MAX_BEAT * 1.5:
            beats.append(line)
            continue
        # Long paragraph: break it at sentence ends so the timings mean
        # something, and let the report say it was split.
        parts = [p.strip() for p in SENT_RE.findall(danda_text(line)) if p.strip()]
        buf = ""
        for part in parts:
            candidate = (buf + " " + part).strip()
            if buf and len(words(candidate)) / wps > MAX_BEAT:
                beats.append(buf)
                buf = part
            else:
                buf = candidate
        if buf:
            beats.append(buf)
    return beats


def analyse(raw, wpm=None, target=None):
    lang = lang_of(raw)
    if wpm is None:
        wpm = WPM_EN if lang == "en" else WPM_HI
    wps = wpm / 60.0
    beats = split_beats(raw, wps)
    if not beats:
        return None

    rows, clock = [], 0.0
    for i, text in enumerate(beats):
        n = len(words(text))
        dur = n / wps
        rows.append({
            "n": i + 1,
            "start": round(clock, 2),
            "dur": round(dur, 2),
            "words": n,
            "text": text,
            # "five hours" is as concrete as "5 hours" once it is said out loud.
            "concrete": len(CONCRETE_RE.findall(text)) + sum(
                1 for w in words(text) if w.lower() in SPOKEN_NUMBERS or w.lower() in MONEY_WORDS)
                + len(hi_number_hits([deva_fold(w) for w in words(text)])),
            "label": "",
            "flags": [],
        })
        clock += dur
    total = clock

    # Label the structural positions a Reel is actually built around.
    for r in rows:
        if r["n"] == 1 or r["start"] + r["dur"] <= HOOK_WINDOW:
            r["label"] = "HOOK"
    rows[-1]["label"] = "CTA" if rows[-1]["label"] != "HOOK" else "HOOK/CTA"
    half = total / 2
    for r in rows:
        if not r["label"] and r["start"] <= half < r["start"] + r["dur"]:
            r["label"] = "MID"

    notes = []
    if rows[0]["dur"] > HOOK_WINDOW:
        rows[0]["flags"].append(f"hook runs {rows[0]['dur']:.1f}s, past the {HOOK_WINDOW:.0f}s mark")
        notes.append(f"Beat 1 takes {rows[0]['dur']:.1f}s to say. Cut it to "
                     f"{int(HOOK_WINDOW * wps)} words or fewer, or the hook lands after "
                     "the decision has been made.")
    if rows[0]["concrete"] == 0:
        notes.append("Beat 1 has no number and no name in it. Hooks without something "
                     "checkable are the ones that get scrolled.")

    for r in rows:
        if r["dur"] > MAX_BEAT:
            r["flags"].append(f"{r['dur']:.1f}s on one beat")
    long_beats = [r["n"] for r in rows if r["dur"] > MAX_BEAT]
    if long_beats:
        notes.append(f"Beat(s) {', '.join(map(str, long_beats))} run past {MAX_BEAT:.0f}s. "
                     "Either split the line or change what is on screen inside it. "
                     "A static frame is where people leave.")

    run, start = 0, None
    for r in rows:
        if r["concrete"] == 0:
            run += 1
            start = start if start is not None else r["n"]
            if run == ABSTRACT_RUN:
                notes.append(f"Beats {start}-{r['n']} have nothing concrete in them. "
                             "Put a number, a name or a price in one of them.")
        else:
            run, start = 0, None

    # Does the last line hand you back to the first one?
    first = {deva_fold(w.lower()) for w in words(rows[0]["text"])
             if w.lower() not in STOPWORDS and deva_fold(w) not in HI_STOPWORDS}
    last = {deva_fold(w.lower()) for w in words(rows[-1]["text"])
            if w.lower() not in STOPWORDS and deva_fold(w) not in HI_STOPWORDS}
    loop = sorted(pretty(w) for w in first & last)
    if loop:
        notes.append(f"Loops: the last beat repeats \"{', '.join(loop[:3])}\" from the hook. "
                     "Second watches are free reach.")
    else:
        notes.append("No loop. The last beat shares no word with the hook, so the video "
                     "ends flat. Echoing one word from beat 1 is the cheapest replay you get.")

    if target:
        delta = total - target
        if abs(delta) <= target * 0.1:
            notes.append(f"Length is on target ({total:.1f}s against {target}s).")
        elif delta > 0:
            notes.append(f"{delta:.1f}s over target. Cut about {int(delta * wps)} words.")
        else:
            notes.append(f"{-delta:.1f}s under target. Either add {int(-delta * wps)} words "
                         "or shoot it short. Short is usually right.")

    a = {
        "wpm": wpm, "target": target,
        "total_seconds": round(total, 2),
        "total_words": sum(r["words"] for r in rows),
        "beats": rows,
        "notes": notes,
    }
    if lang != "en":                         # English output stays exactly as it was
        a["lang"] = lang
    return a


def render(a, out=sys.stdout):
    head = (f"BEAT SHEET  ·  {a['total_words']} words  ·  ~{a['total_seconds']:.1f}s "
            f"at {a['wpm']} wpm" + (f"  ·  target {a['target']}s" if a["target"] else "")
            + (f"  ·  {a['lang']}" if "lang" in a else ""))
    print("\n" + head, file=out)
    print("=" * max(len(head), 72), file=out)
    for r in a["beats"]:
        label = f"{r['label']:<8}" if r["label"] else " " * 8
        print(f"  {tc(r['start'])}  {r['dur']:4.1f}s  {label}{r['text']}", file=out)
        for f in r["flags"]:
            print(f"  {'':>6}  {'':>5}  {'':<8}^ {f}", file=out)
    print("-" * max(len(head), 72), file=out)
    for n in a["notes"]:
        print(f"  - {n}", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Time a Reel script into a beat sheet.")
    ap.add_argument("input", nargs="?", default="-", help="script file, or - for stdin")
    ap.add_argument("--wpm", type=float, default=None,
                    help=f"speaking rate (default {WPM_EN}, or {WPM_HI} for Hindi and mixed scripts)")
    ap.add_argument("--target", type=float, help="target length in seconds")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    a = analyse(raw, wpm=args.wpm, target=args.target)
    if not a:
        print("empty script", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
humanize.py - strip the machine fingerprint out of a draft.

Three passes, in this order:

  1. INVISIBLE   delete or normalise the characters a human keyboard never
                 produces: zero-width joiners, word joiners, soft hyphens,
                 BOMs, Unicode tag characters, non-breaking and narrow spaces.
                 These survive copy-paste and are the most mechanical tell in
                 any generated text.
  2. TYPOGRAPHIC em dash -> comma, en dash -> hyphen, curly quotes -> straight,
                 ellipsis -> three dots, bullet -> hyphen.
  3. LEXICAL     replace the slop lexicon in slop.json with plain words,
                 preserving capitalisation and leaving URLs untouched.

Structural tells (rule-of-three, "not just X, it's Y", hashtag walls) are
REPORTED, never auto-rewritten - rewriting a sentence's shape needs judgement,
so that is the model's job, not a regex's.

Usage
  python3 humanize.py draft.txt
  python3 humanize.py draft.txt --report
  pbpaste | python3 humanize.py - --report
  python3 humanize.py draft.txt --json
  python3 humanize.py draft.txt -o clean.txt
"""

import argparse
import json
import os
import re
import sys
import unicodedata

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


HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "slop.json")

URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")
SENT_RE = re.compile(r"(?:[^.!?\n" + DANDA + r"]|(?<=\d)\.(?=\d))+[.!?" + DANDA + "]*")   # same as detect.py
# A zero-width joiner or non-joiner between two Devanagari letters is spelling:
# it picks the half or full form of a conjunct, such as a half क before ष.
# Deleting it changes how the word is drawn, so those are kept. Anywhere
# else they still go.
JOINERS = "\u200c\u200d"
DEVA_JOINER_RE = re.compile("(?<=[" + DEVA + "])[" + JOINERS + "](?=[" + DEVA + "])")


def load_lexicon(path=LEX):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cp(spec):
    """'U+200B' -> '\\u200b';  'U+E0000-U+E007F' -> (start, end)."""
    if "-" in spec:
        a, b = spec.split("-")
        return (int(a[2:], 16), int(b[2:], 16))
    return int(spec[2:], 16)


def protect_urls(text):
    """Swap URLs for placeholders so no pass rewrites inside a link."""
    found = []

    def stash(m):
        found.append(m.group(0))
        return f"\x00URL{len(found) - 1}\x00"

    return URL_RE.sub(stash, text), found


def restore_urls(text, found):
    for i, url in enumerate(found):
        text = text.replace(f"\x00URL{i}\x00", url)
    return text


def pass_invisible(text, lex):
    """Delete or space-normalise invisible characters. Returns (text, hits)."""
    hits = []
    for entry in lex["invisible"]:
        cp = _cp(entry["cp"])
        if isinstance(cp, tuple):
            pattern = "[" + re.escape(chr(cp[0])) + "-" + re.escape(chr(cp[1])) + "]"
        elif chr(cp) in JOINERS:
            c = re.escape(chr(cp))
            pattern = "(?<![" + DEVA + "])" + c + "|" + c + "(?![" + DEVA + "])"
        else:
            pattern = re.escape(chr(cp))
        n = len(re.findall(pattern, text))
        if n:
            hits.append({"name": entry["cp"] + " " + entry["name"], "count": n,
                         "action": entry["action"]})
            text = re.sub(pattern, "" if entry["action"] == "delete" else " ", text)
    # Any remaining Cf (format) character is invisible by definition.
    kept = {m.start() for m in DEVA_JOINER_RE.finditer(text)}
    stray = [c for i, c in enumerate(text) if unicodedata.category(c) == "Cf" and i not in kept]
    if stray:
        hits.append({"name": "other invisible format chars", "count": len(stray),
                     "action": "delete"})
        text = "".join(c for i, c in enumerate(text)
                       if unicodedata.category(c) != "Cf" or i in kept)
    return text, hits


def pass_typographic(text, lex):
    hits = []
    for entry in lex["typographic"]:
        ch = entry["from"]
        n = text.count(ch)
        if not n:
            continue
        hits.append({"name": f"{ch} {entry['name']}", "count": n, "to": entry["to"].strip() or "(space)"})
        if ch == "—":
            # " word — word " and "word—word" both collapse to a comma + space.
            text = re.sub(r"\s*—\s*", ", ", text)
        elif ch == "–":
            text = re.sub(r"\s*–\s*(?=\d)", "-", text)      # 5–10  -> 5-10
            text = re.sub(r"\s+–\s+", ", ", text)            # used as em dash
            text = text.replace("–", "-")
        else:
            text = text.replace(ch, entry["to"])
    # A comma inserted before existing punctuation reads wrong.
    text = re.sub(r",\s*([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*\n", "\n", text)
    return text, hits


def _match_case(src, repl):
    if not repl:
        return repl
    if src.isupper() and len(src) > 1:
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def phrase_pattern(find):
    """Lexicon entry -> regex. Commas between words are optional, so
    "run don't walk" also catches "Run, don't walk,". Either apostrophe
    matches. \\b goes only on an edge that is a word character, so an entry
    ending in "?" can match at all. Same as detect.py."""
    body = r",?\s+".join(re.escape(part).replace("'", "['’]") for part in find.split())
    head = r"\b" if re.match(r"\w", find) else ""
    tail = r"\b" if re.search(r"\w$", find) else ""
    return re.compile(head + body + tail, re.IGNORECASE)


# A conjunction left with nothing to join after a deletion. A \x00 before the
# space is the end of a protected sentence (see KEEP_RE), so it counts as a
# sentence boundary too.
DANGLING_SENTENCE = re.compile(
    r"(?im)(^|[.!?][ \t]+|\x00[ \t]+)[ \t]*(?:and|or|but|plus)[ \t]*[.!?]+[ \t]*")
DANGLING_TAIL = re.compile(r"(?i)[,;]?[ \t]+(?:and|or|but|plus)[ \t]*([.!?])")
# The same shapes written on purpose: "And?" on its own line, "But." as a beat,
# "Cats, or?". They are masked before any deletion and put back afterwards, so
# the cleanup above only ever removes a conjunction a deletion orphaned.
KEEP_RE = re.compile(
    r"(?im)(?:(?:^|(?<=[.!?] )|(?<=[.!?]\t))[ \t]*|[,;]?[ \t]+)(?:and|or|but|plus)[ \t]*[.!?]+")
HAS_TEXT = re.compile(r"[A-Za-z0-9#@\x00" + DEVA + "]")   # \x00: a line holding a protected sentence


def pass_lexical(text, lex):
    """Replace slop words and phrases. Longest first so phrases win."""
    hits = []
    kept = []

    def keep(m):
        # The placeholder keeps the sentence's final mark, so the clean-up
        # below still sees "and." + "." as doubled punctuation.
        kept.append(m.group(0))
        return f"\x00KEEP{len(kept) - 1}\x00{m.group(0)[-1]}"

    text = KEEP_RE.sub(keep, text)
    original_lines = {l.strip() for l in text.splitlines()}
    deleted = False
    entries = sorted(lex["phrases"] + lex["words"],
                     key=lambda e: len(e["find"]), reverse=True)
    for entry in entries:
        find = entry["find"]
        pattern = phrase_pattern(find)
        found = pattern.findall(text)
        if not found:
            continue
        hits.append({"find": find, "replace": entry["replace"] or "(deleted)",
                     "count": len(found), "family": entry["family"]})
        deleted = deleted or not entry["replace"]
        text = pattern.sub(lambda m: _match_case(m.group(0), entry["replace"]), text)
    # Clean up after deletions. Deleting a whole clause leaves orphaned
    # punctuation behind ("system. ." or a line that now opens on a comma),
    # and that reads worse than the slop did.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?m)^[ \t]*(?:[,.;:]+[ \t]*)+", "", text)
    text = re.sub(r"(?m)^[ \t](?=\S)", "", text)       # one space left by a deletion.
                                                      # Deeper indents are deliberate.
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*([,.;:!?])", r"\1", text)      # an em dash became a comma,
                                                      # then the clause after it went
    text = text.replace("...", "\x00ELL\x00")          # protect real ellipses
    text = re.sub(r"\.\s*\.+", ".", text)
    text = re.sub(r"([!?])\s*\.", r"\1", text)
    text = text.replace("\x00ELL\x00", "...")
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # An em dash that became a comma, followed by a sentence connective, leaves
    # a splice ("is important, also, it's proof"). Promote it to a full stop.
    text = re.sub(r",\s*(also|so|still|basically|in the end)\s*,\s*",
                  lambda m: ". " + m.group(1)[0].upper() + m.group(1)[1:] + ", ", text)
    if deleted:
        # Deleting "follow for more" out of "Follow for more and tag someone
        # who needs this!" used to leave "And!". Only runs when something was
        # actually deleted, so a writer's own "and" is never touched.
        text = DANGLING_SENTENCE.sub(lambda m: m.group(1), text)   # "And!" -> ""
        text = DANGLING_TAIL.sub(r"\1", text)                      # "this, and." -> "this."
        # The same leftover after a danda: "बनाइए। Follow for more!" -> "बनाइए।"
        text = re.sub("([" + DANDA + r"])[ \t]*[.!?]+", r"\1", text)
        # A line that had words and now has only an emoji or punctuation left
        # ("Tag someone who needs this 👇" -> "👇") goes too. A line that was
        # emoji-only in the original is the writer's and stays.
        text = "\n".join(l for l in text.split("\n")
                         if HAS_TEXT.search(l) or not l.strip() or l.strip() in original_lines)
        text = re.sub(r"(?m)^[ \t]+(?=\S)", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    for i, original in enumerate(kept):
        text = re.sub(re.escape(f"\x00KEEP{i}\x00") + r"[.!?]?", lambda m: original, text)
    return text, hits


def scan_structures(text, lex):
    flags = []
    for s in lex["structures"]:
        try:
            pattern = re.compile(s["regex"], re.MULTILINE)
        except re.error:
            continue
        found = pattern.findall(text)
        if found:
            flags.append({"name": s["name"], "count": len(found), "fix": s["fix"]})
    # Hindi stock phrases are reported, not rewritten: a Hindi replacement
    # needs a native speaker's ear, so it is the writer's job, not a regex's.
    folded = deva_fold(text)
    for entry in lex.get("hi", []):
        n = len(deva_re(re.escape(entry["find"]).replace("\\ ", r",?\s+")).findall(folded))
        if n:
            flags.append({"name": f"Hindi stock phrase: {entry['find']}", "count": n,
                          "fix": entry["fix"]})
    # Sentence-length uniformity is structural too.
    # Every sentence counts, short ones included - same rule as detect.py BURSTINESS.
    lens = [len(s.split()) for s in SENT_RE.findall(danda_text(text)) if s.split()]
    if len(lens) >= 4:
        mean = sum(lens) / len(lens)
        var = sum((n - mean) ** 2 for n in lens) / len(lens)
        cv = (var ** 0.5) / mean if mean else 0
        if cv < 0.35:
            flags.append({
                "name": f"Uniform sentence length (variation {cv:.2f})",
                "count": len(lens),
                "fix": "Break one sentence in half. Let another run long. Machines write even.",
            })
    return flags


def restore_capitals(original, text):
    """Deleting an opener leaves the next word lower case.

    Only fix it for writers who capitalise their sentences in the first place:
    a deliberately lower-case voice is a style, not an artefact, and shouting
    over it would be exactly the kind of thing this script exists to stop.
    """
    starts = re.findall(r"(?:^|[.!?]\s+|\n)\s*([A-Za-z])", original)
    if not starts or sum(1 for c in starts if c.isupper()) * 2 < len(starts):
        return text
    return re.sub(r"(?:^|(?<=[.!?] )|(?<=[.!?]\n)|(?<=\n))\s*([a-z])",
                  lambda m: m.group(0)[:-1] + m.group(1).upper(), text)


def humanize(text, lex):
    raw_for_case = text
    text, urls = protect_urls(text)
    text, inv = pass_invisible(text, lex)
    text, typo = pass_typographic(text, lex)
    text, lexi = pass_lexical(text, lex)
    text = restore_capitals(raw_for_case, text)
    text = restore_urls(text, urls)
    return text.strip() + "\n", {
        "invisible": inv,
        "typographic": typo,
        "lexical": lexi,
        "structures": scan_structures(text, lex),
    }


def render_report(report, out=sys.stderr):
    def head(title):
        print(f"\n{title}\n" + "-" * len(title), file=out)

    total = sum(h["count"] for h in report["invisible"]) \
        + sum(h["count"] for h in report["typographic"]) \
        + sum(h["count"] for h in report["lexical"])

    head("HUMANIZE REPORT")
    print(f"{total} machine artefacts removed, "
          f"{len(report['structures'])} structural tells flagged for rewrite", file=out)

    if report["invisible"]:
        head("1. INVISIBLE CHARACTERS")
        for h in report["invisible"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['action']}", file=out)
    if report["typographic"]:
        head("2. TYPOGRAPHY")
        for h in report["typographic"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['to']}", file=out)
    if report["lexical"]:
        head("3. SLOP LEXICON")
        for h in report["lexical"]:
            print(f"  {h['count']:>3}x  {h['find']}  -> {h['replace']}   [{h['family']}]", file=out)
    if report["structures"]:
        head("4. STRUCTURAL TELLS  (not auto-fixed - rewrite these yourself)")
        for h in report["structures"]:
            print(f"  {h['count']:>3}x  {h['name']}\n        {h['fix']}", file=out)
    if not any(report.values()):
        head("CLEAN")
        print("  Nothing to strip.", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Strip the machine fingerprint out of a draft.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("-o", "--out", help="write cleaned text here instead of stdout")
    ap.add_argument("--report", action="store_true", help="print what changed, to stderr")
    ap.add_argument("--json", action="store_true", help="emit {text, report} as JSON")
    ap.add_argument("--lexicon", default=LEX, help="path to slop.json")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    lex = load_lexicon(args.lexicon)
    clean, report = humanize(raw, lex)

    if args.json:
        print(json.dumps({"text": clean, "report": report}, indent=2, ensure_ascii=False))
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(clean)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(clean)
    if args.report:
        render_report(report)


if __name__ == "__main__":
    main()

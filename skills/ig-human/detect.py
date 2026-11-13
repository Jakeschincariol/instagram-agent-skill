#!/usr/bin/env python3
"""
detect.py - a five-check panel that scores how machine-written a draft looks.

What this is:  five local heuristics modelled on the signals public AI
detectors actually measure - sentence-length variation, concreteness, stock
vocabulary, typographic fingerprint, and voice. Every score is computed on
your machine from the text alone. Nothing is uploaded.

What this is NOT:  GPTZero, Originality, Copyleaks, Winston or Turnitin.
It does not call their APIs and it cannot promise their verdict. It catches
the things they all key on, which is why fixing them tends to move their
numbers too - but the only honest claim is the one on this line.

Each check returns a HUMAN score from 0 to 100. Higher is better. A check the
text is too short to measure (BURSTINESS under 4 sentences, SPECIFICITY under
25 words) is reported as n/a and left out of the verdict; VOICE on a short text
is judged on structural tells alone. PASS needs all five checks measured and
passed. If even one could not be measured, a text that would otherwise pass is
INCONCLUSIVE, with no score: too little was measured to vouch for it. A
measured failure is still REVIEW or FLAGGED. URLs and email addresses are
taken out before counting words and sentences, so a link cannot carry a short
draft over the minimums.

Exit status (text mode): 0 PASS, 1 REVIEW or FLAGGED, 3 INCONCLUSIVE.
--json always exits 0; read "verdict", "checks_judged" and "complete".

Usage
  python3 detect.py draft.txt
  pbpaste | python3 detect.py -
  python3 detect.py draft.txt --json
  python3 detect.py before.txt after.txt      # compare two drafts
"""

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "slop.json")

# A full stop between two digits ($18.5k, 3.5 hours) is a decimal point, not
# the end of a sentence.
SENT_RE = re.compile(r"(?:[^.!?\n]|(?<=\d)\.(?=\d))+[.!?]*")
WORD_RE = re.compile(r"[A-Za-z']+")
CONTRACTIONS = re.compile(r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE)
PRONOUNS = re.compile(r"\b(i|me|my|mine|we|us|our|you|your)\b", re.IGNORECASE)
NUMBERS = re.compile(r"\b\d[\d,.]*%?\b|\$\d")
PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)
URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")   # same as humanize.py

# Spoken numbers are as concrete as digits: "five hours" is "5 hours" said out
# loud. Mirrors SPOKEN_NUMBERS / MONEY_WORDS in ig-reel/hookscore.py; kept as a
# copy so ig-human still works when it is installed on its own.
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

# Below these sizes a check has nothing to measure. It is reported as n/a and
# left out of the verdict, instead of being scored a flat 50 - which used to
# cap every comment, DM, reply and bio at 62-67 and made PASS impossible.
MIN_SENTENCES = 4        # BURSTINESS needs a distribution to measure
MIN_WORDS = 25           # SPECIFICITY and the rate half of VOICE need a denominator

# A clean bill of health needs all five checks. If any one could not be
# measured the panel cannot vouch for the text, so if nothing measured failed
# the verdict is INCONCLUSIVE and no score is given, rather than a PASS built
# on part of the evidence ("Ok." once scored 100.0 PASS on three checks, and a
# three-sentence DM 77.0 PASS with no rhythm check). A failure that was
# measured is still a failure: REVIEW and FLAGGED are reported on a partial
# panel, marked as partial.


def clamp(n):
    return max(0.0, min(100.0, n))


def scale(value, human, machine):
    """Map value onto 0-100 where `human` -> 100 and `machine` -> 0."""
    if human == machine:
        return 50.0
    return clamp((value - machine) / (human - machine) * 100)


def prose(text):
    """The draft with URLs and email addresses taken out. A link is an address,
    not writing: its words must not count toward the 25-word minimum, its dots
    must not count as sentence ends, and its numbers are not concrete detail.
    A full stop or bracket the link swallowed is kept, so the sentence it ended
    still ends."""
    return URL_RE.sub(lambda m: re.search(r"[.,;:!?)\]]*$", m.group(0)).group(0), text)


def sentences(text):
    # Every sentence counts, including the two-word ones. "Nobody hunts." is
    # exactly the kind of short line a human uses to vary the rhythm, and
    # dropping it made burstiness blind to the thing it measures.
    return [s.strip() for s in SENT_RE.findall(text) if s.split()]


def words(text):
    return WORD_RE.findall(text)


def phrase_pattern(find):
    """Lexicon entry -> regex. Commas between words are optional, so
    "run don't walk" also catches "Run, don't walk,". A straight apostrophe
    also matches a curly one, because this scores the raw draft. \\b goes only
    on an edge that is a word character: "what are your thoughts?" ends on "?",
    and a \\b after it never matched anything. Same as humanize.py."""
    body = r",?\s+".join(re.escape(part).replace("'", "['’]") for part in find.split())
    head = r"\b" if re.match(r"\w", find) else ""
    tail = r"\b" if re.search(r"\w$", find) else ""
    return re.compile(head + body + tail, re.IGNORECASE)


def check_burstiness(text):
    """Humans vary sentence length hard. Models write even."""
    lens = [len(s.split()) for s in sentences(text)]
    if len(lens) < MIN_SENTENCES:
        return None, f"n/a: {len(lens)} sentence(s), needs {MIN_SENTENCES}+ to measure variation"
    mean = statistics.mean(lens)
    cv = statistics.pstdev(lens) / mean if mean else 0
    score = scale(cv, human=0.70, machine=0.22)
    return score, f"variation {cv:.2f} across {len(lens)} sentences (want 0.55+)"


def check_specificity(text):
    """Numbers, names and concrete nouns. Slop is abstract."""
    w = words(text)
    if len(w) < MIN_WORDS:
        return None, f"n/a: {len(w)} words, needs {MIN_WORDS}+ for a density"
    per100 = 100 / len(w)
    spoken = [x for x in (t.lower() for t in w) if x in SPOKEN_NUMBERS or x in MONEY_WORDS]
    hits = len(NUMBERS.findall(text)) + len(set(PROPER.findall(text))) + len(spoken)
    density = hits * per100
    score = scale(density, human=6.0, machine=0.5)
    return score, f"{hits} concrete markers, {density:.1f} per 100 words (want 4+)"


def check_slop(text, lex):
    """Stock vocabulary density against the lexicon."""
    # run() passes prose(): humanize.py never rewrites inside a URL, so
    # scoring the words in one left a penalty nothing could fix.
    w = words(text)
    if not w:
        return 50.0, "empty"
    hits, found = 0, []
    for entry in lex["words"] + lex["phrases"]:
        pattern = phrase_pattern(entry["find"])
        n = len(pattern.findall(text))
        if n:
            hits += n
            found.append(entry["find"])
    density = hits * 100 / len(w)
    score = scale(density, human=0.0, machine=4.0)
    detail = f"{hits} stock terms, {density:.1f} per 100 words"
    if found:
        detail += " (" + ", ".join(sorted(found)[:4]) + (", ..." if len(found) > 4 else "") + ")"
    return score, detail


def check_fingerprint(text):
    """Characters a phone keyboard does not produce."""
    invisible = sum(1 for c in text if unicodedata.category(c) == "Cf")
    em = text.count("—")
    curly = sum(text.count(c) for c in "‘’“”")
    ellip = text.count("…")
    nbsp = sum(text.count(c) for c in "   ")
    total = invisible * 4 + em * 2 + curly + ellip + nbsp
    per1k = total * 1000 / max(len(text), 1)
    score = scale(per1k, human=0.0, machine=12.0)
    detail = (f"{invisible} invisible, {em} em dash, {curly} curly quote, "
              f"{ellip} ellipsis, {nbsp} hard space")
    return score, detail


def check_voice(text, lex):
    """Contractions, person, and the shapes models default to."""
    w = words(text)
    tells = 0
    names = []
    for s in lex["structures"]:
        try:
            n = len(re.compile(s["regex"], re.MULTILINE).findall(text))
        except re.error:
            continue
        if n:
            tells += n
            names.append(s["id"])
    if len(w) < MIN_WORDS:
        # Too few words for contraction and pronoun rates to mean anything,
        # but a structural tell is still a tell - and in a one-line comment it
        # is most of the text, so each one costs half the score.
        detail = f"short text: structural tells only, {tells} found"
        if names:
            detail += " [" + ", ".join(names[:4]) + "]"
        return clamp(100 - tells * 50), detail
    per100 = 100 / len(w)
    contractions = len(CONTRACTIONS.findall(text)) * per100
    person = len(PRONOUNS.findall(text)) * per100
    bullets = [len(b.split()) for b in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", text)]
    uniform = (len(bullets) >= 3 and statistics.pstdev(bullets) < 1.6)
    score = (scale(contractions, human=3.0, machine=0.0) * 0.35
             + scale(person, human=8.0, machine=1.0) * 0.35
             + clamp(100 - tells * 22) * 0.30)
    if uniform:
        score -= 12
        names.append("uniform-bullets")
    detail = (f"{contractions:.1f} contractions, {person:.1f} personal pronouns "
              f"per 100 words, {tells} structural tell(s)")
    if names:
        detail += " [" + ", ".join(names[:4]) + "]"
    return clamp(score), detail


CHECKS = ["BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"]


def run(text, lex):
    results = {}
    body = prose(text)                       # links out of every count
    results["BURSTINESS"] = check_burstiness(body)
    results["SPECIFICITY"] = check_specificity(body)
    results["SLOP DENSITY"] = check_slop(body, lex)
    results["FINGERPRINT"] = check_fingerprint(text)   # a hidden char is a tell anywhere
    results["VOICE"] = check_voice(body, lex)
    # Checks that had nothing to measure (n/a) are left out. SLOP DENSITY,
    # FINGERPRINT and VOICE always score, so there are never fewer than three.
    scores = [results[c][0] for c in CHECKS if results[c][0] is not None]
    # The weakest check drags the verdict: a detector only needs one signal.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4
    verdict = "PASS" if overall >= 70 and min(scores) >= 55 else (
        "REVIEW" if overall >= 50 else "FLAGGED")
    if verdict == "PASS" and len(scores) < len(CHECKS):
        # Nothing measured failed, but too little was measured to say so.
        return results, None, "INCONCLUSIVE"
    return results, overall, verdict


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render(results, overall, verdict, label=None, out=sys.stdout):
    title = "AI DETECTION PANEL" + (f"  -  {label}" if label else "")
    print("\n" + title, file=out)
    print("=" * max(len(title), 62), file=out)
    for name in CHECKS:
        score, detail = results[name]
        if score is None:
            print(f"  {name:<13} {'-' * 24}   n/a", file=out)
        else:
            print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    judged = [c for c in CHECKS if results[c][0] is not None]
    if overall is None:
        print(f"  {'HUMAN SCORE':<13} {'-' * 24}   n/a   {verdict}", file=out)
    else:
        print(f"  {'HUMAN SCORE':<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    if len(judged) < len(CHECKS):
        partial = " - partial score" if overall is not None else ""
        print(f"  {'':<13} short text: judged on {len(judged)} of {len(CHECKS)} checks{partial}",
              file=out)
    if verdict == "INCONCLUSIVE":
        print(f"\n  Too short to vouch for. Nothing measured failed, but a PASS needs all "
              f"{len(CHECKS)} checks:\n  {MIN_WORDS}+ words and {MIN_SENTENCES}+ sentences, "
              "links not counted. Check humanize.py found\n  nothing to strip or flag, then "
              "read it out loud.", file=out)
    elif verdict != "PASS":
        weakest = min(judged, key=lambda c: results[c][0])
        print(f"\n  Weakest signal: {weakest}. Fix that first.", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Score how machine-written a draft looks.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("compare", nargs="?", help="second file, to show before/after")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lexicon", default=LEX)
    args = ap.parse_args()

    lex = json.load(open(args.lexicon, encoding="utf-8"))
    read = lambda p: sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read()

    targets = [(args.input, read(args.input))]
    if args.compare:
        targets.append((args.compare, read(args.compare)))

    payload = []
    for name, text in targets:
        results, overall, verdict = run(text, lex)
        payload.append({
            "source": name,
            "checks": {k: {"score": None if v[0] is None else round(v[0], 1), "detail": v[1]}
                       for k, v in results.items()},
            "human_score": None if overall is None else round(overall, 1),
            "verdict": verdict,
            "checks_judged": sum(1 for v in results.values() if v[0] is not None),
            "complete": all(v[0] is not None for v in results.values()),
        })

    if args.json:
        print(json.dumps(payload if args.compare else payload[0], indent=2))
        return

    for (name, text), p in zip(targets, payload):
        results, overall, verdict = run(text, lex)
        render(results, overall, verdict, label=os.path.basename(name) if args.compare else None)
    if args.compare:
        a, b = payload
        fmt = lambda p: "n/a" if p["human_score"] is None else f"{p['human_score']:.1f}"
        delta = ("" if None in (a["human_score"], b["human_score"])
                 else f"   ({b['human_score'] - a['human_score']:+.1f})")
        print(f"  {fmt(a)} {a['verdict']}  ->  {fmt(b)} {b['verdict']}{delta}\n")

    # 0 PASS, 1 REVIEW or FLAGGED, 3 INCONCLUSIVE (too short to judge).
    sys.exit({"PASS": 0, "INCONCLUSIVE": 3}.get(payload[-1]["verdict"], 1))


if __name__ == "__main__":
    main()

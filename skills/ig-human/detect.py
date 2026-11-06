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

Each check returns a HUMAN score from 0 to 100. Higher is better.

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


def _mark_class():
    """Every combining mark in the BMP, as the inside of a regex class.

    Devanagari vowel signs, Arabic harakat and decomposed accents are
    category M, which \\w does not match. Without them a Hindi word breaks
    into pieces at every vowel sign. ZWNJ and ZWJ sit inside words in Urdu,
    Persian and the Indic scripts, so they count as part of a word too.
    """
    ranges, start, prev = [], None, None
    for cp in range(0x0300, 0x10000):
        if unicodedata.category(chr(cp))[0] == "M":
            start = cp if start is None else start
            prev = cp
        elif start is not None:
            ranges.append((start, prev))
            start = None
    return "".join(re.escape(chr(a)) + ("-" + re.escape(chr(b)) if b > a else "")
                   for a, b in ranges) + "\u200c\u200d"


MARKS = _mark_class()
# Sentence ends in Hindi (danda) and Urdu (full stop, question mark) too.
SENT_RE = re.compile(r"[^.!?\u0964\u0965\u06d4\u061f\n]+[.!?\u0964\u0965\u06d4\u061f]*")
# Letters in any script, with their combining marks, and the apostrophe.
WORD_RE = re.compile(r"(?:[^\W\d_]|['" + MARKS + r"])+")
CONTRACTIONS = re.compile(r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE)
PRONOUNS = re.compile(
    r"\b(i|me|my|mine|we|us|our|you|your"
    r"|yo|m[í i]|mis|mío|mía|nosotros|nuestro|nuestra|nuestros|nuestras"
    r"|vos|te|ti|tu|tus|tuyo|tuya|usted|ustedes|les|nos)\b", re.IGNORECASE)
NUMBERS = re.compile(r"\b\d[\d,.]*%?\b|\$\d")
PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-ZÁÉÍÓÚÑ][a-záéíóúñü]{2,}\b", re.MULTILINE)


def clamp(n):
    return max(0.0, min(100.0, n))


# ---------------------------------------------------------------------------
# Rioplatense Spanish.
#
# The word lists were not the whole problem. check_voice puts 35% of its weight
# on contraction density ("don't", "I'm"), and Spanish has no apostrophe
# contractions at all, so every Spanish text scored zero on that third no matter
# how it was written. What follows replaces that measure, for Spanish only, with
# the real local equivalent of spoken register: voseo, filler words and
# diminutives.
# ---------------------------------------------------------------------------

ES_HINT = re.compile(
    r"[ñÑ¿¡]|\b(?:de|que|el|la|los|las|un|una|por|para|con|en|es|se|"
    r"y|no|más|pero|como|su|sus)\b", re.IGNORECASE)

# Voseo verb forms and filler words: what stands in for the contraction here.
ES_SPOKEN = re.compile(
    r"\b(?:tenés|querés|podés|sabés|hacés|decís|venís|sos|andás|tené|mirá|"
    r"escuchá|fijate|acordate|dale|che|posta|obvio|tipo|igual|ojo|pará|bueno|"
    r"nada|o sea|viste|re|súper|un toque|al toque|de una|ni ahí|capaz)\b",
    re.IGNORECASE)

# Diminutives: a strong marker of informal register in this dialect.
ES_DIM = re.compile(r"\b\w{3,}(?:ito|ita|itos|itas)\b", re.IGNORECASE)
ES_DIM_FALSE = {
    "favorito", "favorita", "favoritos", "favoritas", "éxito", "exito",
    "infinito", "infinita", "delito", "circuito", "gratuito", "gratuita",
    "requisito", "depósito", "deposito", "propósito", "proposito",
    "apetito", "bonito", "bonita", "distrito", "mérito", "merito",
    "granito", "transito", "tránsito", "maldito", "escrito", "margarita",
}


def is_spanish(text):
    """Cheap and good enough: the text carries enye/accents or Spanish stopwords."""
    hits = len(ES_HINT.findall(text))
    w = max(1, len(WORD_RE.findall(text)))
    return hits * 100 / w > 12


def es_spoken_density(text, per100):
    """What contractions measure in English: how much this sounds spoken."""
    n = len(ES_SPOKEN.findall(text))
    n += len([d for d in ES_DIM.findall(text)
              if d.lower() not in ES_DIM_FALSE])
    return n * per100


def clamp(n):
    return max(0.0, min(100.0, n))


def scale(value, human, machine):
    """Map value onto 0-100 where `human` -> 100 and `machine` -> 0."""
    if human == machine:
        return 50.0
    return clamp((value - machine) / (human - machine) * 100)


def sentences(text):
    return [s.strip() for s in SENT_RE.findall(text) if len(s.split()) > 2]


def non_latin(text):
    """True when most letters are not Latin: Devanagari, Arabic, Cyrillic.

    The slop lexicon, contractions and pronouns are English, and names are
    found by their capital letter. On a script those cannot read, the check
    goes neutral instead of calling the text machine-written.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if unicodedata.name(c, "").startswith("LATIN"))
    return latin * 2 < len(letters)


NA = 50.0                # neutral: counts in the average, never as the weakest.


def words(text):
    return WORD_RE.findall(text)


def check_burstiness(text):
    """Humans vary sentence length hard. Models write even."""
    lens = [len(s.split()) for s in sentences(text)]
    if len(lens) < 4:
        return 50.0, "too short to judge"
    mean = statistics.mean(lens)
    cv = statistics.pstdev(lens) / mean if mean else 0
    score = scale(cv, human=0.70, machine=0.22)
    return score, f"variation {cv:.2f} across {len(lens)} sentences (want 0.55+)"


def check_specificity(text):
    """Numbers, names and concrete nouns. Slop is abstract."""
    w = words(text)
    if len(w) < 25:
        return 50.0, "too short to judge"
    per100 = 100 / len(w)
    hits = len(NUMBERS.findall(text)) + len(set(PROPER.findall(text)))
    density = hits * per100
    score = scale(density, human=6.0, machine=0.5)
    if non_latin(text) and score < NA:
        return NA, (f"n/a: {hits} number(s), {density:.1f} per 100 words; names need "
                    "capital letters, so they cannot be counted in this script")
    return score, f"{hits} concrete markers, {density:.1f} per 100 words (want 4+)"


def phrase_pattern(find):
    """Match a lexicon entry as a whole phrase. The \\b goes only on an edge
    that is a word character: "what are your thoughts?" ends on a "?", and a
    \\b after it never matches at the end of a line."""
    body = re.escape(find).replace(r"\ ", r"\s+")
    head = r"\b" if re.match(r"\w", find) else ""
    tail = r"\b" if re.search(r"\w$", find) else ""
    return re.compile(head + body + tail, re.IGNORECASE)


def check_slop(text, lex):
    """Stock vocabulary density against the lexicon."""
    w = words(text)
    if not w:
        return 50.0, "empty"
    if non_latin(text):
        return NA, "n/a: the slop lexicon is English"
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
    if len(w) < 25:
        return 50.0, "too short to judge"
    if non_latin(text):
        return NA, "n/a: contractions and pronouns are only read in English"
    per100 = 100 / len(w)
    if is_spanish(text):
        contractions = es_spoken_density(text, per100)
        spoken_label = "spoken-register markers"
    else:
        contractions = len(CONTRACTIONS.findall(text)) * per100
        spoken_label = "contractions"
    person = len(PRONOUNS.findall(text)) * per100
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
    bullets = [len(b.split()) for b in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", text)]
    uniform = (len(bullets) >= 3 and statistics.pstdev(bullets) < 1.6)
    score = (scale(contractions, human=3.0, machine=0.0) * 0.35
             + scale(person, human=8.0, machine=1.0) * 0.35
             + clamp(100 - tells * 22) * 0.30)
    if uniform:
        score -= 12
        names.append("uniform-bullets")
    detail = (f"{contractions:.1f} {spoken_label}, {person:.1f} personal pronouns "
              f"per 100 words, {tells} structural tell(s)")
    if names:
        detail += " [" + ", ".join(names[:4]) + "]"
    return clamp(score), detail


def applies(result):
    return not result[1].startswith("n/a")


CHECKS = ["BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"]


def run(text, lex):
    results = {}
    results["BURSTINESS"] = check_burstiness(text)
    results["SPECIFICITY"] = check_specificity(text)
    results["SLOP DENSITY"] = check_slop(text, lex)
    results["FINGERPRINT"] = check_fingerprint(text)
    results["VOICE"] = check_voice(text, lex)
    scores = [results[c][0] for c in CHECKS]
    # The weakest check drags the verdict: a detector only needs one signal.
    # A check marked n/a could not read the script, so it is never the weakest.
    applied = [results[c][0] for c in CHECKS if applies(results[c])] or scores
    overall = statistics.mean(scores) * 0.6 + min(applied) * 0.4
    verdict = "PASS" if overall >= 70 and min(applied) >= 55 else (
        "REVIEW" if overall >= 50 else "FLAGGED")
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
        print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HUMAN SCORE':<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    if verdict != "PASS":
        pool = [c for c in CHECKS if applies(results[c])] or CHECKS
        weakest = min(pool, key=lambda c: results[c][0])
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
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "human_score": round(overall, 1),
            "verdict": verdict,
        })

    if args.json:
        print(json.dumps(payload if args.compare else payload[0], indent=2))
        return

    for (name, text), p in zip(targets, payload):
        results, overall, verdict = run(text, lex)
        render(results, overall, verdict, label=os.path.basename(name) if args.compare else None)
    if args.compare:
        a, b = payload
        delta = b["human_score"] - a["human_score"]
        print(f"  {a['human_score']:.1f} {a['verdict']}  ->  "
              f"{b['human_score']:.1f} {b['verdict']}   ({delta:+.1f})\n")

    sys.exit(0 if payload[-1]["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()

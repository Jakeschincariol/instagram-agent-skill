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
"""

import argparse
import json
import re
import statistics
import sys
import unicodedata


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
# Letters and digits in any script, plus the marks that belong to them, plus
# the $ % ' ’ - that the English version always kept inside a word.
WORD_RE = re.compile(r"(?:[^\W_]|[$%'’\-" + MARKS + r"])+")
NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"                       # money, whole
    r"|\b\d[\d,]*(?:\.\d+)?\s?"                      # a figure, with or
    r"(?:%|k\b|x\b|hrs?\b|hours?\b|mins?\b|minutes?\b"  # without a unit
    r"|days?\b|weeks?\b|months?\b|years?\b)?",
    re.IGNORECASE)
PROPER_RE = re.compile(r"(?<!^)\b[A-ZÁÉÍÓÚÑ][a-záéíóúñü]{2,}\b")
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


# Rioplatense Spanish.
#
# The five checks above were written against English word lists, so a hook
# written in Spanish scored WEAK however good it was: "cinco veces" was not a
# number and "pará" was not tension. These sets extend the English ones rather
# than replacing them, so both languages score and neither regresses.
#
# Voseo throughout, because that is how the hook gets said out loud here.
# Accents are kept meaningful: "pará" (stop) is tension, "para" (for) is a
# preposition, and collapsing the two would put a tension marker in every line.
# ---------------------------------------------------------------------------

SPOKEN_NUMBERS_ES = {
    "cero", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
    "nueve", "diez", "once", "doce", "quince", "veinte", "treinta",
    "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa",
    "cien", "ciento", "mil", "millón", "millon", "millones", "docena",
    "decena", "media", "mitad", "doble", "triple",
}

MONEY_WORDS_ES = {
    "pesos", "peso", "dólares", "dolares", "dólar", "dolar", "mangos",
    "guita", "luca", "lucas", "palo", "palos", "centavos", "plata",
    "porciento", "ganancia", "facturación", "sueldo", "alquiler",
    "descuento", "precio", "presupuesto",
}

STAKES_ES = {
    # frenar, negar
    "pará", "pare", "frena", "frená", "nunca", "jamás", "jamas", "nadie",
    "ninguno", "ninguna", "ni", "tampoco", "sin", "nada",
    # error y pérdida
    "mal", "error", "errores", "equivocado", "equivocada", "equivocas",
    "perdí", "perder", "perdiendo", "perdés", "perdiste", "pérdida",
    "cuesta", "costó", "costo", "roto", "rota", "arruina", "arruinás",
    "arruinar", "fracasó", "fracaso", "falla", "fallé", "daña", "dañar",
    "lastima", "enferma", "tóxico", "toxico", "venenoso",
    # plata y trueque
    "gratis", "pagué", "pagar", "pagás", "cobré", "ahorré", "ahorrás",
    "ahorrar", "regalado", "carito", "caro", "barato",
    # revelación
    "verdad", "mito", "mentira", "mentí", "mienten", "secreto", "escondido",
    "oculto", "prohibido", "ilegal", "estafa", "trampa",
    # juicio
    "peor", "odio", "odiás", "desperdicio", "desperdiciás",
    # giro
    "antes", "hasta", "salvo", "pero", "excepto", "igual", "encima",
    "realmente", "todavía", "todavia", "ya", "recién", "recien",
    "problema", "riesgo", "peligro", "cuidado", "ojo", "advertencia",
    "arrepentí", "deberías", "deberia", "debería", "contra", "versus",
    "dejá", "dejar", "borrá", "borrar", "cortá", "primero",
}

WEAK_OPENERS_ES = [
    "bueno", "ok", "okey", "oka", "hola", "holis", "buenas", "che",
    "chicos", "chicas", "gente", "amigos", "bienvenidos", "bienvenidas",
    "hoy", "básicamente", "basicamente", "sinceramente", "la verdad",
    "mirá que", "escuchen", "escuchá que", "o sea", "digamos", "nada",
    "quería", "quiero", "les quiero", "les voy", "te voy", "uno de",
    "una de", "en este", "en el", "esto es", "acá les", "acá te",
    "esta es", "este es", "resulta que", "les cuento", "te cuento",
]

IMPERATIVES_ES = {
    "pará", "mirá", "mira", "escuchá", "probá", "guardá", "usá",
    "hacé", "armá", "escribí", "mandá", "llevá", "empezá", "dejá",
    "fijate", "acordate", "anotá", "copiá", "robá", "borrá", "comprá",
    "vení", "dale", "pedí", "elegí", "leé", "contá", "sumá", "revisá",
    "ojo", "nunca", "siempre", "no", "andá", "sacá", "poné", "tené",
}

SPOKEN_NUMBERS |= SPOKEN_NUMBERS_ES
MONEY_WORDS |= MONEY_WORDS_ES
STAKES |= STAKES_ES
IMPERATIVES |= IMPERATIVES_ES
WEAK_OPENERS = WEAK_OPENERS + WEAK_OPENERS_ES

DEALBREAKERS += [
    (re.compile(r"(?i)^\s*[¿¡]?\s*(?:no pares de scrollear|pará de scrollear"
                r"|no sigas scrolleando|freu?ná el scroll)"),
     "Abre pidiendo atención. Si la tuvieras no haría falta pedirla."),
    (re.compile(r"(?i)\b(?:en este (?:video|reel)|en el video de hoy"
                r"|te voy a (?:mostrar|contar|enseñar)"
                r"|les voy a (?:mostrar|contar|enseñar)"
                r"|hoy les traigo|hoy te traigo)\b"),
     "Preámbulo de video. Borralo y abrí directo en lo que promete."),
    (re.compile(r"(?i)^\s*[¿¡]?\s*(?:hola|holis|buenas|qué onda|que onda|che\b"
                r"|bienvenid[oa]s)"),
     "Saludo. Nadie entra al feed para que lo saluden."),
]




def clamp(n):
    return max(0.0, min(100.0, n))


def non_latin(text):
    """True when most letters are not Latin: Devanagari, Arabic, Cyrillic.

    The word lists below (stakes, openers, pronouns, spoken numbers) are
    English, and the name check needs capitals. On a script they cannot read,
    those checks go neutral instead of scoring the line as if it said nothing.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if unicodedata.name(c, "").startswith("LATIN"))
    return latin * 2 < len(letters)


NA = 50.0                # a check that cannot read this script. Neutral: it
                         # counts in the average, never as the weakest check.


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def check_length(text):
    """A hook has to land before the thumb moves. Roughly two seconds."""
    w = words(text)
    n = len(w)
    secs = n / 2.75                      # ~165 words per minute, spoken
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
    low = [w.lower().strip("'’") for w in words(text)]
    spoken = [w for w in low if w in SPOKEN_NUMBERS or w in MONEY_WORDS]
    hits = len(nums) + len(propers) + len(spoken)
    if hits == 0 and non_latin(text):
        return NA, "n/a: no digits, and names and spoken numbers are only read in English"
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join(nums[:2] + sorted(propers)[:2] + spoken[:2])
    return score, (f"{hits} concrete marker(s)" + (f": {found}" if found else
                   " - no number, no name, nothing checkable"))


def check_stakes(text):
    """Tension, cost, negation. Something the viewer might lose."""
    w = [x.lower().strip("'’") for x in words(text)]
    hits = [x for x in w if x in STAKES]
    markers = sorted(set(hits))
    if re.search(r"\$\s?\d", text):
        markers.append("a price")
    if not markers and non_latin(text):
        return NA, "n/a: the stakes word list is English"
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
    low = [x.lower().strip("'’") for x in w]
    if non_latin(text):
        # Only numbers can be found in a script the word lists do not cover.
        # A number up front is a payload; no number proves nothing either way.
        for i, token in enumerate(w[:4]):
            if NUMBER_RE.match(token):
                return 100.0, f"payload at word {i + 1}"
        return NA, "n/a: payload words are only read in English; no number in the first 4 words"
    opener = " ".join(low[:2])
    penalty = 0
    hit_opener = None
    for weak in WEAK_OPENERS:
        if opener.startswith(weak) or low[0] == weak:
            penalty, hit_opener = 30, weak
            break
    payload = None
    for i, token in enumerate(low):
        if (token in STAKES or token in SPOKEN_NUMBERS or token in MONEY_WORDS
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
    w = [x.lower().strip("'’") for x in words(text)]
    if non_latin(text):
        return NA, "n/a: pronouns are only read in English"
    if re.search(r"\b(you|your|you're|youre|yourself)\b", low):
        return 100.0, "speaks to the viewer"
    # Spanish second person, including the voseo verb forms that carry it
    # without a pronoun in front. Without this every Spanish hook fell through
    # to third person and lost the check outright, whoever it was aimed at.
    if re.search(r"\b(vos|tu|tus|tuyo|tuya|te|ti|usted|ustedes"
                 r"|ten\u00e9s|quer\u00e9s|pod\u00e9s|sab\u00e9s|hac\u00e9s|sos|viste|dec\u00eds"
                 r"|compr\u00e1s|pag\u00e1s|perd\u00e9s)\b", low):
        return 100.0, "speaks to the viewer"
    if w and w[0] in IMPERATIVES:
        return 90.0, f"imperative opener (\"{w[0]}\")"
    if re.search(r"\b(i|my|me|we|our)\b", low):
        return 70.0, "first person, no viewer named"
    if re.search(r"\b(yo|mi|mis|me|nosotros|nuestro|nuestra)\b", low):
        return 70.0, "first person, no viewer named"
    return 35.0, "third person, nobody in the room"


def applies(result):
    return not result[1].startswith("n/a")


def weakest_check(results):
    pool = [c for c in CHECKS if applies(results[c])] or CHECKS
    return min(pool, key=lambda c: results[c][0])


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
    scores = [results[c][0] for c in CHECKS]
    # The weakest property caps the hook, same logic as detect.py: one bad
    # property is enough for the thumb to keep moving. A check marked n/a
    # could not read the script, so it is never the weakest one.
    applied = [results[c][0] for c in CHECKS if applies(results[c])] or scores
    overall = statistics.mean(scores) * 0.6 + min(applied) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(applied) >= 55 and not flags else (
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
        weakest = weakest_check(results)
        print(f"\n  Weakest property: {weakest}. Fix that one and re-run.", file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout):
    print("\nHOOK RANKING\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        print(f"{mark} {r['score']:5.1f} {r['verdict']:<7} {hook}", file=out)
        print(f"        weakest: {r['weakest']} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        dealbreaker: {f}", file=out)
    print("\nShoot the top one. If the top one is under 50, none of these are the hook.\n",
          file=out)


def main():
    ap = argparse.ArgumentParser(description="Score a Reel hook on five properties.")
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
        payload.append({
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": weakest_check(results),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
        })

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

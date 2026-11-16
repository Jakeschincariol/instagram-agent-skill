#!/usr/bin/env python3
"""
swipe.py - rank reels you collected by how far they beat their own account,
name the hook formula each one used, and write the swipe file.

The point of this script is one correction: raw views are not evidence. A
2,000,000-follower account doing 400,000 views had a quiet day. A 4,000-
follower account doing 400,000 views found something. This ranks on the
multiple over the account's own baseline, which is the only version of
"went viral" that tells you anything you can copy.

Input is a tab-separated file you fill in while you browse, one reel per row,
with a header line naming the columns:

    account   followers   median   views    hook
    @someone  48000       11000    412000   nobody tells you your first 30 flop

`median` is that account's typical recent views and is the better baseline.
If you only have `followers`, leave median out and the script says so.
`hook` is the first line of the reel, spoken or on screen, in their words.

Usage
  python3 swipe.py captured.tsv
  python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
  python3 swipe.py captured.tsv --json
"""

import argparse
import json
import os
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


HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..", "ig-reel", "hooks.json")
WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+|" + DEVA_WORD_RE.pattern)

try:                                              # optional: score the hooks too
    sys.path.insert(0, os.path.join(HERE, "..", "ig-reel"))
    from hookscore import run as score_hook       # noqa: E402
except Exception:                                 # ig-viral copied on its own
    score_hook = None


def load_formulas(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    by_id = {h["id"]: h for h in d["hooks"]}
    order = d.get("classify_order") or sorted(by_id)
    # match_hi is the Hindi version of a formula's pattern, optional. It is
    # matched as whole words against deva_fold(hook), and only for hooks that
    # have Devanagari in them, so English hooks are named exactly as before.
    return [(by_id[i]["id"], by_id[i]["name"],
             re.compile(by_id[i]["match"], re.IGNORECASE),
             deva_re(by_id[i]["match_hi"]) if by_id[i].get("match_hi") else None)
            for i in order if i in by_id]


def classify(hook, formulas):
    if not formulas:
        return None, "unclassified"
    hindi = lang_of(hook) != "en"
    folded = deva_fold(hook)
    for fid, name, pattern, hi_pattern in formulas:
        if pattern.search(hook) or (hindi and hi_pattern and hi_pattern.search(folded)):
            return fid, name
    return None, "unclassified"


def parse_seconds(value):
    """'24', '24s', '0:24', '1:05', '1:02:03' -> seconds. None if unreadable."""
    m = re.search(r"\d+(?::\d{1,2}){0,2}(?:\.\d+)?", value or "")
    if not m:
        return None
    total = 0.0
    for part in m.group(0).split(":"):      # each colon shifts the rest by 60
        total = total * 60 + float(part)
    return total


def read_rows(path):
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    lines = [l for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return []
    head = [c.strip().lower() for c in lines[0].split("\t")]
    if "views" in head and "hook" in head:
        cols, body = head, lines[1:]
    else:
        cols, body = ["account", "followers", "views", "hook"], lines
    rows = []
    for line in body:
        cells = line.split("\t")
        if len(cells) < len(cols):
            cells += [""] * (len(cols) - len(cells))
        r = dict(zip(cols, [c.strip() for c in cells]))
        try:
            r["views"] = int(re.sub(r"[^\d]", "", r.get("views", "")) or 0)
        except ValueError:
            continue
        for k in ("followers", "median"):
            digits = re.sub(r"[^\d]", "", r.get(k, "") or "")
            r[k] = int(digits) if digits else None
        # Optional columns the skill asks you to capture. Absent or blank is fine.
        r["length_s"] = parse_seconds(r.get("length", ""))
        r["cta"] = (r.get("cta") or "").strip()
        r["on_screen"] = (r.get("on-screen") or r.get("onscreen") or r.get("on_screen") or "").strip()
        if r["views"] and r.get("hook"):
            rows.append(r)
    return rows


def analyse(rows, formulas):
    used_median = any(r.get("median") for r in rows)
    for r in rows:
        base = r.get("median") or r.get("followers") or 0
        r["baseline"] = base
        r["outlier"] = round(r["views"] / base, 2) if base else None
        r["formula_id"], r["formula"] = classify(r["hook"], formulas)
        r["words"] = len(WORD_RE.findall(r["hook"]))
        if lang_of(r["hook"]) != "en":       # English rows stay exactly as they were
            r["lang"] = lang_of(r["hook"])
        if score_hook:
            _, overall, verdict, _ = score_hook(r["hook"])
            r["hook_score"], r["hook_verdict"] = round(overall, 1), verdict
        else:
            r["hook_score"], r["hook_verdict"] = None, None
    ranked = sorted(rows, key=lambda r: -(r["outlier"] or 0))
    third = max(1, len(ranked) // 3)
    top, bottom = ranked[:third], ranked[-third:]

    def med(items, key):
        vals = [i[key] for i in items if i.get(key) is not None]
        return round(statistics.median(vals), 1) if vals else None

    counts = {}
    for r in top:
        counts[r["formula"]] = counts.get(r["formula"], 0) + 1

    def cta_kind(cta):
        low = cta.lower()
        if not low:
            return None
        return "comment a keyword" if low.startswith("comment") else low.split()[0]

    def tally(items):
        c = {}
        for i in items:
            k = cta_kind(i["cta"])
            if k:
                c[k] = c.get(k, 0) + 1
        return sorted(c.items(), key=lambda kv: -kv[1])

    has_onscreen = "on-screen" in rows[0] or "onscreen" in rows[0] or "on_screen" in rows[0]
    return {
        "baseline": "account median" if used_median else "follower count",
        "n": len(ranked),
        "accounts": len({r.get("account", "") for r in ranked}),
        "reels": ranked,
        "top_formulas": sorted(counts.items(), key=lambda kv: -kv[1]),
        "top_hook_score": med(top, "hook_score"),
        "bottom_hook_score": med(bottom, "hook_score"),
        "top_words": med(top, "words"),
        "bottom_words": med(bottom, "words"),
        "unclassified": sum(1 for r in ranked if r["formula"] == "unclassified"),
        # Structure, from the optional columns: None / [] when not captured.
        "top_length": med(top, "length_s"),
        "bottom_length": med(bottom, "length_s"),
        "top_ctas": tally(top),
        "bottom_ctas": tally(bottom),
        "top_onscreen": (sum(1 for r in top if r["on_screen"]), len(top)) if has_onscreen else None,
        "bottom_onscreen": (sum(1 for r in bottom if r["on_screen"]), len(bottom)) if has_onscreen else None,
    }


def render(a, out=sys.stdout):
    head = (f"SWIPE FILE  ·  {a['n']} reels  ·  {a['accounts']} accounts  ·  "
            f"baseline: {a['baseline']}")
    print("\n" + head, file=out)
    print("=" * max(len(head), 78), file=out)
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "   ?"
        score = f"{r['hook_score']:.0f}" if r["hook_score"] is not None else " -"
        fid = f"#{r['formula_id']:<2}" if r["formula_id"] else "-  "
        print(f"  {mult:>7}  hook {score:>3}  {fid} {r['formula'][:22]:<22} "
              f"{r.get('account', '')[:16]:<16} {r['views']:>9,}", file=out)
        print(f"           \"{r['hook'][:96]}\"", file=out)
    print("-" * max(len(head), 78), file=out)
    print("WHAT IS WORKING IN THIS BATCH", file=out)
    if a["top_formulas"]:
        print("  top third by outlier:  "
              + ", ".join(f"{n} x{c}" for n, c in a["top_formulas"][:4]), file=out)
    if a["top_hook_score"] is not None:
        print(f"  median hook score:     top {a['top_hook_score']:.0f}  "
              f"vs bottom {a['bottom_hook_score']:.0f}", file=out)
    print(f"  median hook length:    top {a['top_words']} words  "
          f"vs bottom {a['bottom_words']} words", file=out)
    if a["top_length"] is not None and a["bottom_length"] is not None:
        print(f"  median length:         top {a['top_length']:g}s  "
              f"vs bottom {a['bottom_length']:g}s", file=out)
    if a["top_ctas"] or a["bottom_ctas"]:
        fmt = lambda c: ", ".join(f"{k} x{n}" for k, n in c) or "none captured"
        print(f"  cta, top third:        {fmt(a['top_ctas'])}", file=out)
        print(f"  cta, bottom third:     {fmt(a['bottom_ctas'])}", file=out)
    if a["top_onscreen"]:
        (tn, tt), (bn, bt) = a["top_onscreen"], a["bottom_onscreen"]
        print(f"  on-screen card:        top {tn}/{tt}  vs bottom {bn}/{bt}", file=out)
    print(f"  unclassified:          {a['unclassified']} of {a['n']}. Read those by hand, "
          "they are where a formula you do not have yet is hiding.", file=out)
    print("\n  A hand-collected batch is evidence, not proof. Twelve reels shows you "
          "nothing;\n  forty across six accounts shows you something. Collect more before "
          "you believe it.\n", file=out)


def to_markdown(a):
    lines = ["# Swipe file", "",
             f"{a['n']} reels across {a['accounts']} accounts. "
             f"Ranked by multiple over {a['baseline']}.", ""]
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "?"
        lines += [f"## {mult}  {r['formula']}  ({r.get('account', '')})",
                  f"- views: {r['views']:,}  baseline: {r['baseline']:,}",
                  f"- hook score: {r['hook_score']}  words: {r['words']}",
                  f"- hook: \"{r['hook']}\""]
        extra = [f"- on-screen: {r['on_screen']}" if r["on_screen"] else "",
                 f"- length: {r['length_s']:g}s" if r["length_s"] is not None else "",
                 f"- cta: {r['cta']}" if r["cta"] else ""]
        lines += [e for e in extra if e] + [""]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Rank collected reels by outlier multiple.")
    ap.add_argument("input", nargs="?", default="-", help="TSV file, or - for stdin")
    ap.add_argument("--hooks", default=HOOKS, help="path to ig-reel/hooks.json")
    ap.add_argument("--out", help="also write the swipe file as markdown here")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = read_rows(args.input)
    if not rows:
        print("no usable rows. Need a tab-separated file with at least views and hook.",
              file=sys.stderr)
        sys.exit(2)
    formulas = load_formulas(args.hooks)
    a = analyse(rows, formulas)
    if not formulas:
        print("note: hooks.json not found, formulas not named. Pass --hooks.", file=sys.stderr)
    if score_hook is None:
        print("note: hookscore.py not importable, hook scores skipped.", file=sys.stderr)

    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    if args.out:
        path = os.path.expanduser(args.out)
        if os.path.dirname(path):            # "swipe.md" has no directory part
            os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(to_markdown(a))
        print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()

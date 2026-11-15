#!/usr/bin/env python3
"""
caption.py - lint an Instagram caption and show exactly what the feed shows
before the "... more".

Instagram gives a caption about 125 characters in the feed and hides the rest
behind a tap. Almost every caption that fails, fails there: the hook is in
sentence three, or the first line is a greeting, or the whole thing opens on a
hashtag. This prints the visible window as a box so you can read it the way a
scrolling stranger does, then runs the checks worth running: length, the first
line (greeting, emoji, hashtag, cut), a concrete hook, hashtags and where they
sit, links, one ask, a typeable keyword, emoji density and search terms.

The 125-character cut is an approximation. The real number moves with the
device, the font size and where your line breaks fall, which is exactly why
you want a margin rather than a caption engineered to end at 125. Change it
with --truncate if you want to test a tighter one.

Usage
  python3 caption.py caption.txt
  python3 caption.py caption.txt --keywords "proposal software,client contract"
  pbpaste | python3 caption.py -
  python3 caption.py caption.txt --json
"""

import argparse
import json
import re
import sys
import textwrap

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


LIMIT = 2200             # Instagram's hard caption limit.
TRUNCATE = 125           # Roughly where the feed cuts to "... more".
HASHTAG_LIMIT = 5        # Instagram's cap per post or reel since 18 Dec 2025,
                         # down from 30. Announced by the @Creators account:
                         # "using fewer (up to 5) more targeted hashtags,
                         # rather than many generic ones, can improve both your
                         # content's performance and people's experience".

HASHTAG_RE = re.compile(r"(?:^|\s)(#[A-Za-z0-9_" + DEVA + "]+)")    # #बजट is a tag too
MENTION_RE = re.compile(r"(?:^|\s)(@[A-Za-z0-9_.]+)")
LINK_RE = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|co|io|net|org|ai|app)/\S*",
                     re.IGNORECASE)
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿←-⇿️]")
# A capitalised word counts as a name only mid-sentence. The first word of a
# line or of a sentence ("Hey guys! Quick one") is capitalised by grammar, not
# because it names anything.
CONCRETE_RE = re.compile(r"\$\s?\d|\b\d[\d,.]*\b|(?<!^)(?<![.!?]\s)\b[A-Z][a-z]{2,}\b",
                         re.MULTILINE)

# The keyword has to be one word in capitals that people can type: COMMENT
# CONTRACT works, comment "the contract guide" does not. Only "comment" and
# "the word" are case-insensitive; the keyword itself is not.
KEYWORD_ASK = re.compile(r"(?i:\bcomment\s+(?:the\s+word\s+)?)[\"“']?[A-Z][A-Z0-9]+\b(?![a-z])")
# Something that looks like a keyword ask but is not typeable: a quoted phrase,
# a lower-case word, or an emoji where the keyword should be.
LOOSE_KEYWORD_ASK = re.compile(
    r"(?i:\bcomment\s+(?:the\s+word\s+)?)"
    r"(?:[\"“'][^\"”'\n]+[\"”']"
    r"|(?!(?:below|here|your|my|it|this|that|with|if|on|and|or|what|which|the|a|an|down|"
    r"for|to|in|now|too|back|please)\b)[a-z][a-z0-9]*\b"
    r"|[^\w\s\"“'])")
# A greeting word has to stand alone: followed by a space, punctuation or the
# end of the line, never a hyphen or another letter. "Hi-res", "Hiring",
# "Yours" and "Superfans" are not greetings. Bare "welcome" is left out too:
# "Welcome to the only template you need" is a hook, "Welcome back" is not.
GREETING_RE = re.compile(
    r"(?i)^\s*(?:hey|hi|hello|hiya|howdy|yo|sup|gm|good (?:morning|afternoon|evening|day)"
    r"|what'?s up|welcome back|happy (?:\w+day|friday|weekend))(?![\w'’-])")

ASKS = [
    (KEYWORD_ASK, "comment a keyword"),
    (re.compile(r"(?i)\b(?:dm|message) me\b"), "DM me"),
    (re.compile(r"(?i)\bsave (?:this|it)\b"), "save this"),
    (re.compile(r"(?i)\bshare (?:this|it)\b"), "share this"),
    (re.compile(r"(?i)\bfollow (?:me|for)\b"), "follow"),
    (re.compile(r"(?i)\blink in (?:my )?bio\b"), "link in bio"),
    (re.compile(r"(?i)\b(?:swipe|tap) (?:through|left|right|for|to)\b"), "swipe or tap"),
    (re.compile(r"(?i)\btell me\b|\bwhat would you\b|\bwhich one\b"), "answer a question"),
]

# Hindi and Hinglish versions of the same checks. They only run on text that
# has Devanagari in it (lang_of is not "en"), and they match deva_fold(text).
# "Comment में GUIDE लिखिए" is one typeable keyword ask, the same as
# "Comment GUIDE". A Devanagari or lower-case keyword is a loose one: most
# people type comments on an English keyboard, so capitals are what works.
HI_WRITE = (r"(?:लिखिए|लिखें|लिखो|लिख दीजिए|लिख दें|लिख दो|लिखना|कमेंट करें|कमेंट कीजिए|कमेंट करो"
            r"|comment करें|comment कीजिए|comment करो)")
HI_COMMENT = r"(?i:comment|कमेंट|कॉमेंट|कमेन्ट)(?:\s+(?:में|मे|बॉक्स में|box में))?"
HI_COMMENT_VERB = r"(?:\s+(?:करो|करें|कीजिए|करिए|कर दो|कर दीजिए|कर दें))?"   # "Comment करो GUIDE"
HI_KEYWORD_ASK = re.compile(deva_fold(
    HI_COMMENT + HI_COMMENT_VERB + r"\s+[\"“']?(?P<kw>[A-Z][A-Z0-9]+)\b(?![a-z])"
    r"|(?<![\w\"“'])[\"“']?(?P<kw2>[A-Z][A-Z0-9]+)[\"”']?\s+" + HI_WRITE))
# The Devanagari class is added after folding: deva_fold would read the "-" of
# a character range as a hyphen inside a compound word.
HI_LOOSE_KEYWORD_ASK = re.compile(
    deva_fold(HI_COMMENT + HI_COMMENT_VERB
              + r"\s+(?!(?:में|मे)\s)(?:[\"“'][^\"”'\n]+[\"”']|(?-i:[a-z][a-z0-9]*)|")
    + "[" + DEVA + "]+" + deva_fold(r")\s+" + HI_WRITE))
HI_ASKS = [(deva_re(p), name) for p, name in [
    (r"(?:dm|डीएम|मैसेज|message|inbox|इनबॉक्स)\s+(?:(?:में|पर)\s+)?(?:[^\s।.!?]+\s+){0,2}?"
     r"(?:कीजिए|करें|करो|करिए|कर दीजिए|कर दें|भेजिए|भेज दीजिए|भेजें|भेज दें|भेजो|भेज दो)"
     r"|(?:मुझे|मुझको|हमें)\s+(?:[^\s।.!?]+\s+){0,2}?(?:भेजिए|भेज दीजिए|भेजें|भेज दें|भेजो|भेज दो)", "DM me"),
    (r"(?:save|सेव)\s+(?:कर\s+)?(?:लीजिए|लें|लो|करें|कीजिए|करिए|रखिए|रखें)", "save this"),
    (r"(?:share|शेयर)\s+(?:कीजिए|करें|करो|करिए|कर दीजिए|कर दें)", "share this"),
    (r"(?:follow|फॉलो|फ़ॉलो)\s+(?:कीजिए|करें|करो|करिए|कर लीजिए|कर लें)", "follow"),
    (r"(?:bio|बायो)\s+(?:में|मे)\s+(?:link|लिंक)|(?:link|लिंक)\s+(?:bio|बायो)\s+(?:में|मे)", "link in bio"),
    (r"(?:swipe|स्वाइप)\s+(?:कीजिए|करें|करो|करिए)", "swipe or tap"),
    (r"बताइए|बताइये|बताएं|बताएँ|बताओ|आपकी राय", "answer a question"),
]]
HI_GREETING_RE = deva_re(
    r"^\s*(?:नमस्ते|नमस्कार|प्रणाम|हेलो|हैलो|हाय|जय जोहार|राम राम|सुप्रभात|शुभ प्रभात"
    r"|गुड मॉर्निंग|दोस्तों|दोस्तो)")
# "भेज दीजिए" on its own is a share ask ("अपने भाई को भेज दीजिए"), unless the
# same sentence is about a DM or about sending to me ("DM में GUIDE भेजिए",
# "मुझे भेज दीजिए"): that is the DM ask above, not a share.
HI_SEND_RE = deva_re(r"भेज दीजिए|भेज दें|भेज दो|भेजिए|भेजें|भेजो")
HI_DM_CONTEXT_RE = deva_re(r"dm|डीएम|मैसेज|message|inbox|इनबॉक्स|मुझे|मुझको|हमें")
HI_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|" + DEVA_WORD_RE.pattern)


def hi_asks(folded):
    found = []
    clauses = re.split("[.!?\n" + DANDA + "]", danda_text(folded))
    for pattern, name in HI_ASKS:
        hit = pattern.search(folded)
        if not hit and name == "share this":
            hit = any(HI_SEND_RE.search(c) and not HI_DM_CONTEXT_RE.search(c) for c in clauses)
        if hit:
            found.append(name)
    return found

FILLER_TAGS = {"#viral", "#fyp", "#explore", "#explorepage", "#foryou", "#foryoupage",
               "#trending", "#instagood", "#love", "#follow", "#like4like", "#reels",
               "#reelsinstagram", "#viralreels", "#instadaily"}


def visible_window(text, cut):
    """What the feed shows. Instagram cuts mid-word, so this does too."""
    flat = text.strip()
    return flat if len(flat) <= cut else flat[:cut]


def render_box(window, truncated, out=sys.stdout, width=52):
    print("\n  WHAT THE FEED SHOWS", file=out)
    print("  +" + "-" * (width + 2) + "+", file=out)
    lines = []
    for raw in window.split("\n"):
        lines.extend(textwrap.wrap(raw, width) or [""])
    for line in lines[:8]:
        print(f"  | {line:<{width}} |", file=out)
    tail = "... more" if truncated else "(whole caption fits)"
    print("  +" + "-" * (width + 2 - len(tail) - 2) + f" {tail} " + "+", file=out)


def analyse(text, cut=TRUNCATE, keywords=None):
    text = text.rstrip()
    stripped = text.strip()
    chars = len(stripped)
    lines = [l for l in stripped.split("\n")]
    first_line = lines[0].strip() if lines else ""
    tags = HASHTAG_RE.findall(stripped)
    mentions = MENTION_RE.findall(stripped)
    links = LINK_RE.findall(stripped)
    emoji = EMOJI_RE.findall(stripped)
    window = visible_window(stripped, cut)
    truncated = chars > cut
    lang = lang_of(stripped)
    folded = deva_fold(stripped)
    asks = [name for pattern, name in ASKS if pattern.search(stripped)]
    keyword = KEYWORD_ASK.search(stripped)
    hi_keyword = None
    if lang != "en":
        asks += [name for name in hi_asks(folded) if name not in asks]
        if not keyword:
            hi_keyword = HI_KEYWORD_ASK.search(folded)
            if hi_keyword and "comment a keyword" not in asks:
                asks.insert(0, "comment a keyword")
    loose = None if keyword or hi_keyword else LOOSE_KEYWORD_ASK.search(stripped)
    if not (keyword or hi_keyword or loose) and lang != "en":
        loose = HI_LOOSE_KEYWORD_ASK.search(folded)
    if loose:
        asks.append("comment a phrase")     # still an ask, just not a typeable one
    filler = [t for t in tags if t.lower() in FILLER_TAGS]
    keywords = [k.strip() for k in (keywords or []) if k.strip()]

    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    add("LENGTH", "FAIL" if chars > LIMIT else "PASS",
        f"{chars} / {LIMIT} characters" + (f", {chars - LIMIT} over the limit"
                                           if chars > LIMIT else ""))

    if not first_line:
        add("FIRST LINE", "FAIL", "the caption opens on a blank line")
    elif first_line.startswith("#") or first_line.startswith("@"):
        add("FIRST LINE", "FAIL",
            "opens on a hashtag or a mention, which is the one position worth a sentence")
    elif EMOJI_RE.match(first_line):
        add("FIRST LINE", "FAIL",
            "opens on an emoji. The first character is worth a word")
    elif GREETING_RE.match(first_line) or (lang != "en" and HI_GREETING_RE.match(deva_fold(first_line))):
        add("FIRST LINE", "FAIL",
            "opens on a greeting. Nobody came to the feed to be greeted; lead with the hook or the ask")
    elif len(first_line) > cut:
        add("FIRST LINE", "WARN",
            f"{len(first_line)} characters, so it gets cut at {cut} mid-thought. "
            "Fine if the cut is a cliffhanger, bad if it is a subordinate clause")
    else:
        add("FIRST LINE", "PASS", f"{len(first_line)} characters, lands whole")

    concrete = len(CONCRETE_RE.findall(window))
    if lang != "en":                         # "पाँच लाख" is as concrete as "5 lakh"
        concrete += len(hi_number_hits(HI_TOKEN_RE.findall(deva_fold(window))))
    add("HOOK IS CONCRETE", "PASS" if concrete else "WARN",
        f"{concrete} number(s) or name(s) in the visible window"
        + ("" if concrete else " - nothing checkable before the tap"))

    if len(tags) > HASHTAG_LIMIT:
        add("HASHTAGS", "FAIL", f"{len(tags)} tags, over Instagram's cap of {HASHTAG_LIMIT}. "
                                "Tags past the fifth do not count and the block reads as old")
    elif len(tags) == HASHTAG_LIMIT and filler:
        add("HASHTAGS", "WARN", f"{len(tags)} tags, at the cap, and "
                                f"{len(filler)} of them generic. Spend the five on topics")
    elif filler:
        add("HASHTAGS", "WARN", f"{len(tags)} tags, {len(filler)} of them generic "
                                f"({', '.join(filler[:3])}). Those describe nothing")
    else:
        add("HASHTAGS", "PASS", f"{len(tags)} tag(s)" + (f": {' '.join(tags)}" if tags else ""))

    if not tags:
        add("TAG PLACEMENT", "PASS", "no tags to place")
    elif any(re.search(r"(?:^|\s)" + re.escape(t) + (r"\b" if t[-1].isascii() else "(?![" + DEVA + "])"),
                       window) for t in tags):
        add("TAG PLACEMENT", "WARN", "a hashtag is inside the visible window, "
                                     "spending feed space on a label")
    else:
        add("TAG PLACEMENT", "PASS", "tags are below the fold")

    add("LINKS", "WARN" if links else "PASS",
        f"{len(links)} link(s) in the caption, and captions are not clickable. "
        f"Move it to the bio or the DM" if links else "no dead links in the body")

    if len(asks) == 1:
        add("ONE ASK", "PASS", f"one call to action: {asks[0]}")
    elif not asks:
        add("ONE ASK", "WARN", "no call to action. Decide what this post is for")
    else:
        add("ONE ASK", "WARN", f"{len(asks)} asks ({', '.join(asks)}). "
                               "Two asks is the same as none")

    if keyword:
        add("KEYWORD ASK", "PASS", f"{keyword.group(0).split()[-1].strip(chr(34) + chr(39) + '“')} "
                                   "is one word in capitals, easy to type")
    elif hi_keyword:
        add("KEYWORD ASK", "PASS", f"{hi_keyword.group('kw') or hi_keyword.group('kw2')} "
                                   "is one word in capitals, easy to type")
    elif loose:
        add("KEYWORD ASK", "WARN", f"{loose.group(0)} - not a keyword people can type. "
                                   "Use one word in capitals, no spaces, no emoji: Comment CONTRACT")

    density = len(emoji) * 100 / max(chars, 1)
    add("EMOJI", "WARN" if density > 4 else "PASS",
        f"{len(emoji)} emoji, {density:.1f} per 100 characters"
        + (" - reads as decoration" if density > 4 else ""))

    if keywords:
        low = stripped.lower()
        found = [k for k in keywords if k.lower() in low]
        missing = [k for k in keywords if k.lower() not in low]
        in_window = [k for k in found if k.lower() in window.lower()]
        status = "PASS" if not missing else ("WARN" if found else "FAIL")
        add("SEARCH TERMS", status,
            f"{len(found)}/{len(keywords)} present"
            + (f", {len(in_window)} in the visible window" if found else "")
            + (f". Missing: {', '.join(missing)}" if missing else ""))

    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    verdict = "FIX" if fails else ("REVIEW" if warns else "READY")

    a = {
        "characters": chars, "limit": LIMIT, "truncate_at": cut,
        "visible": window, "truncated": truncated,
        "first_line_chars": len(first_line),
        "hashtags": tags, "mentions": mentions, "links": links,
        "emoji": len(emoji), "asks": asks,
        "checks": checks, "verdict": verdict,
    }
    if lang != "en":                         # English output stays exactly as it was
        a["lang"] = lang
    return a


def render(a, out=sys.stdout):
    head = (f"CAPTION LINT  ·  {a['characters']} / {a['limit']} chars  ·  "
            f"{len(a['hashtags'])} hashtags  ·  {len(a['asks'])} ask(s)")
    print("\n" + head, file=out)
    print("=" * max(len(head), 62), file=out)
    render_box(a["visible"], a["truncated"], out=out)
    print("", file=out)
    for c in a["checks"]:
        print(f"  {c['status']:<5} {c['check']:<17} {c['detail']}", file=out)
    print("-" * max(len(head), 62), file=out)
    print(f"  VERDICT  {a['verdict']}\n", file=out)


def main():
    ap = argparse.ArgumentParser(description="Lint an Instagram caption.")
    ap.add_argument("input", nargs="?", default="-", help="caption file, or - for stdin")
    ap.add_argument("--truncate", type=int, default=TRUNCATE,
                    help=f"characters shown before '... more' (default {TRUNCATE})")
    ap.add_argument("--keywords", default="", help="comma-separated terms you want to be found for")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    a = analyse(raw, cut=args.truncate, keywords=args.keywords.split(","))
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0 if a["verdict"] == "READY" else 1)


if __name__ == "__main__":
    main()

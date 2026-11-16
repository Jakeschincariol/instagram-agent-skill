#!/usr/bin/env python3
"""Hindi and mixed Hindi-English regression tests.

Same harness as regress.py: every script runs as a subprocess through the
.claude/skills symlinks, from this folder, with no bytecode written. The
fixtures in hi/ are fictional. English behaviour is covered by regress.py,
validate.py and golden.py; the tests here also check that English output
gains no new fields.

  python3 hindi.py            # all tests
  python3 hindi.py L1 L8      # only ids starting with L1 or L8
"""
import importlib.util, json, os, re, shutil, subprocess, sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regress import ENV, HERE, SK, caption, chk, detect, humanize, run  # noqa: E402

TESTS = []
HI = os.path.join(HERE, "hi")
SCRIPTS = ["ig-reel/hookscore.py", "ig-reel/beats.py", "ig-human/detect.py",
           "ig-human/humanize.py", "ig-caption/caption.py", "ig-viral/swipe.py"]
BEGIN, END = "# --- Devanagari support ---", "# --- end of Devanagari support ---"


def test(tid, desc):
    def deco(fn):
        TESTS.append((tid, desc, fn))
        return fn
    return deco


def fixture(name):
    return open(os.path.join(HI, name), encoding="utf-8").read()


def hook(text):
    _, out, _ = run("ig-reel/hookscore.py", "--hook", text, "--json")
    return json.loads(out)


def beats(text, *extra):
    _, out, _ = run("ig-reel/beats.py", "-", "--json", *extra, stdin=text)
    return json.loads(out)


def module(script):
    spec = importlib.util.spec_from_file_location(os.path.basename(script)[:-3] + "_t",
                                                  os.path.join(SK, script))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def block(script):
    src = open(os.path.join(SK, script), encoding="utf-8").read()
    return src[src.index(BEGIN):src.index(END)]


# ======================================================================
# Shared tokenizer
# ======================================================================
@test("L1", "the Devanagari block is identical in all six scripts")
def _():
    first = block(SCRIPTS[0])
    for s in SCRIPTS[1:]:
        assert block(s) == first, f"{s} differs from {SCRIPTS[0]}"


@test("L2", "a Hindi word is one word: the mixed test line counts 7, not 3")
def _():
    d = hook("बिना label पढ़े protein shake मत लीजिए।")
    assert d["checks"]["LENGTH"]["detail"].startswith("7 words"), d["checks"]["LENGTH"]
    m = module("ig-human/detect.py")
    assert m.words("रुकिए पहले") == ["रुकिए", "पहले"]          # \w alone splits रुकिए into र, क, ए


@test("L3", "language detection: en, hi and mixed; links, hashtags and handles not counted")
def _():
    m = module("ig-reel/hookscore.py")
    cases = {"Proposals used to take me five hours.": "en",
             "मेरी पहली दुकान का किराया बारह हज़ार था।": "hi",
             "बिना label पढ़े protein shake मत लीजिए।": "mixed",
             "जिम जाने से पहले ये पढ़िए #fitness #gymlife @someone https://example.com/x": "hi",
             "aap kaise ho": "en"}                         # Hindi in Latin letters: a known limit
    for text, want in cases.items():
        assert m.lang_of(text) == want, (text, m.lang_of(text))


@test("L4", "nukta and candrabindu spellings compare equal (ज़रूरी = जरूरी, पाँच = पांच)")
def _():
    m = module("ig-reel/hookscore.py")
    assert m.deva_fold("ज़रूरी") == m.deva_fold("जरूरी")
    assert m.deva_fold("पाँच") == m.deva_fold("पांच")
    assert m.deva_fold("plain English, café") == "plain English, café"   # untouched
    a = hook("मैंने पाँच लाख रुपये गँवाए।")["checks"]["SPECIFICITY"]["score"]
    b = hook("मैंने पांच लाख रुपये गंवाए।")["checks"]["SPECIFICITY"]["score"]
    assert a == b > 15, (a, b)


@test("L5", "English output gains no new fields: no lang or calibration key in any tool")
def _():
    en = "Proposals used to take me five hours. Now it is twenty minutes. Comment TEMPLATE."
    assert "lang" not in hook(en) and "calibration" not in hook(en)
    assert "lang" not in detect(en) and "lang" not in caption(en) and "lang" not in beats(en)
    _, out, _ = run("ig-viral/swipe.py", "captured.tsv", "--json")
    assert not any("lang" in r for r in json.loads(out)["reels"])


# ======================================================================
# hookscore.py
# ======================================================================
@test("L6", "hookscore: Hindi stakes, numbers and an end-of-line imperative are scored")
def _():
    d = hook("बिना label पढ़े protein shake मत लीजिए।")
    assert d["checks"]["STAKES"]["score"] == 100.0, d["checks"]["STAKES"]
    assert d["checks"]["ADDRESS"]["score"] == 90.0, d["checks"]["ADDRESS"]   # verb comes last in Hindi
    d = hook("आपकी सैलरी से हर महीने पाँच हज़ार रुपये कहाँ जाते हैं?")
    assert d["checks"]["ADDRESS"]["detail"] == "speaks to the viewer", d["checks"]["ADDRESS"]
    assert d["checks"]["SPECIFICITY"]["score"] >= 75, d["checks"]["SPECIFICITY"]
    assert hook("शादी के लिए लोन लिया")["checks"]["ADDRESS"]["score"] != 90.0   # लिए is not a command


@test("L7", "hookscore: Hindi greeting and video preamble are dealbreakers, opener penalised")
def _():
    d = hook("नमस्ते दोस्तों, आज के इस वीडियो में हम बात करेंगे बजट की।")
    assert any(f.startswith("Greeting") for f in d["flags"]), d["flags"]
    assert any(f.startswith("Video preamble") for f in d["flags"]), d["flags"]
    assert "weak opener" in d["checks"]["FRONTLOAD"]["detail"], d["checks"]["FRONTLOAD"]
    assert d["verdict"] == "WEAK", d
    # a word that merely starts like a weak opener is not one: तोड़ is not तो
    assert "weak opener" not in hook("तोड़ दिया मैंने अपना पुराना नियम।")["checks"]["FRONTLOAD"]["detail"]


@test("L8", "hookscore: Hindi scores carry the uncalibrated label, in JSON and in text")
def _():
    d = hook("मैंने एक गलती की और दो लाख रुपये डूब गए।")
    assert d["lang"] == "hi" and d["calibration"].startswith("uncalibrated"), d
    _, out, _ = run("ig-reel/hookscore.py", "--hook", "मैंने एक गलती की और दो लाख रुपये डूब गए।")
    assert "Language: hi. Score is uncalibrated" in out, out
    _, out, _ = run("ig-reel/hookscore.py", os.path.join("hi", "hooks.txt"))
    assert "[hi]" in out and "[mixed]" in out and "uncalibrated" in out, out


# ======================================================================
# beats.py
# ======================================================================
@test("L9", "beats: a 100-word Hindi script times at 40s (150 wpm); --wpm still wins")
def _():
    a = beats(fixture("script.txt"))
    assert (a["total_words"], a["wpm"], a["lang"]) == (100, 150, "hi"), (a["total_words"], a["wpm"])
    assert abs(a["total_seconds"] - 40.0) < 0.01, a["total_seconds"]
    assert beats(fixture("script.txt"), "--wpm", "165")["wpm"] == 165.0
    assert beats("Proposals used to take me five hours.")["wpm"] == 165     # English default


@test("L10", "beats: । splits a long Hindi paragraph, spoken numbers are concrete, loops seen")
def _():
    para = " ".join(["मैंने तीस दिन तक हर खर्च एक छोटी सी कॉपी में लिखा।"] * 4)
    a = beats(para)
    assert len(a["beats"]) > 1, a["beats"]
    assert a["beats"][0]["concrete"] >= 1, a["beats"][0]
    a = beats(fixture("script.txt"))
    assert any(n.startswith("Loops:") for n in a["notes"]), a["notes"]       # बारह हज़ार returns
    assert not any("है" in n or "का\"" in n for n in a["notes"] if n.startswith("Loops:"))


@test("L11", "beats: copied on its own, the fallback lists and the Hindi block still work")
def _():
    solo = os.path.join(HERE, "solo_beats")
    os.makedirs(solo, exist_ok=True)
    for f in os.listdir(solo):
        os.remove(os.path.join(solo, f))
    shutil.copy(os.path.join(SK, "ig-reel/beats.py"), solo)
    p = subprocess.run([sys.executable, os.path.join(solo, "beats.py"), os.path.join(HI, "script.txt"),
                        "--json"], capture_output=True, text=True, env=ENV, cwd=HERE)
    assert p.returncode == 0, p.stderr[-300:]
    a = json.loads(p.stdout)
    assert (a["total_words"], a["wpm"]) == (100, 150), a["total_words"]


# ======================================================================
# caption.py
# ======================================================================
@test("L12", "caption: 'Comment में GUIDE लिखिए' is one typeable keyword ask (was no ask)")
def _():
    d = caption(fixture("caption_mixed.txt"))
    assert d["asks"] == ["comment a keyword"], d["asks"]
    assert chk(d, "ONE ASK")["status"] == "PASS", chk(d, "ONE ASK")
    k = chk(d, "KEYWORD ASK")
    assert k["status"] == "PASS" and k["detail"].startswith("GUIDE "), k
    assert d["lang"] == "mixed", d.get("lang")
    for line in ("GUIDE कमेंट करें और मैं भेज दूँगा।", "कमेंट में \"GUIDE\" लिखिए"):
        assert chk(caption(line), "KEYWORD ASK")["status"] == "PASS", line


@test("L13", "caption: a Devanagari or lower-case keyword is loose; 'Comment में बताइए' is a question")
def _():
    for line in ("Comment में गाइड लिखिए", "comment में guide लिखिए", "कमेंट में 'पूरी लिस्ट' लिखिए"):
        d = caption(line)
        assert chk(d, "KEYWORD ASK")["status"] == "WARN", (line, d["checks"])
        assert "comment a phrase" in d["asks"], (line, d["asks"])
    d = caption("Comment में बताइए आप क्या करते।")
    assert d["asks"] == ["answer a question"], d["asks"]
    assert not any(c["check"] == "KEYWORD ASK" for c in d["checks"]), d["checks"]


@test("L14", "caption: Hindi greeting fails the first line; Hindi asks counted, 'भेज दूँगा' is not")
def _():
    d = caption(fixture("caption_greeting.txt"))
    assert chk(d, "FIRST LINE")["status"] == "FAIL", chk(d, "FIRST LINE")
    assert d["asks"] == ["save this", "share this"], d["asks"]
    assert chk(d, "ONE ASK")["status"] == "WARN"
    assert "share this" not in caption("मैं आपको checklist भेज दूँगा।")["asks"]
    assert caption("DM कीजिए")["asks"] == ["DM me"]


@test("L15", "caption: Hindi hashtags are tags; Hindi number words make the hook concrete")
def _():
    d = caption("ये बात लंबी है और कहानी भी लंबी है, पर सुनिए।\n\n#बजट #सेहत #fitness")
    assert d["hashtags"] == ["#बजट", "#सेहत", "#fitness"], d["hashtags"]
    assert chk(d, "TAG PLACEMENT")["status"] == "WARN"          # short caption, tags are visible
    assert chk(caption("पाँच लाख की गलती से बचिए।"), "HOOK IS CONCRETE")["status"] == "PASS"
    assert chk(caption("एक गलती से बचिए।"), "HOOK IS CONCRETE")["status"] == "WARN"


# ======================================================================
# detect.py
# ======================================================================
@test("L16", "detect: Hindi words and । sentences are measured, with the uncalibrated label")
def _():
    d = detect(fixture("human_hi.txt"))
    assert d["checks_judged"] == 5 and d["complete"], d["checks"]
    assert "8 sentences" in d["checks"]["BURSTINESS"]["detail"], d["checks"]["BURSTINESS"]
    assert d["lang"] == "hi" and d["calibration"].startswith("uncalibrated"), d
    assert d["checks"]["VOICE"]["detail"].startswith("contractions not measured (hi)"), d["checks"]["VOICE"]
    piped = fixture("human_hi.txt").replace("।", " |")               # keyboards without ।
    assert detect(piped)["checks"]["BURSTINESS"] == d["checks"]["BURSTINESS"]


@test("L17", "detect: Hindi stock phrases count as slop; the stock draft scores below the human one")
def _():
    bad, good = detect(fixture("draft_hi.txt")), detect(fixture("human_hi.txt"))
    assert bad["checks"]["SLOP DENSITY"]["score"] < 50 < good["checks"]["SLOP DENSITY"]["score"], (
        bad["checks"]["SLOP DENSITY"], good["checks"]["SLOP DENSITY"])
    assert bad["human_score"] < good["human_score"], (bad["human_score"], good["human_score"])
    assert bad["verdict"] != "PASS", bad
    # commas between the words do not hide a phrase, the same rule as English
    assert detect("लाइक, शेयर और सब्सक्राइब ज़रूर करें।")["checks"]["SLOP DENSITY"]["score"] < 100


@test("L18", "detect: a joiner inside a Devanagari word is not an invisible-character tell")
def _():
    hindi = "क्\u200cष और क्\u200dष दोनों सही हैं।"
    assert detect(hindi)["checks"]["FINGERPRINT"]["detail"].startswith("0 invisible"), detect(hindi)
    assert detect("zero\u200bwidth here.")["checks"]["FINGERPRINT"]["detail"].startswith("1 invisible")


# ======================================================================
# humanize.py
# ======================================================================
@test("L19", "humanize: a joiner between Devanagari letters survives, English joiners still go")
def _():
    raw = fixture("joiners.txt")
    out = humanize(raw)["text"]
    hindi_line = raw.splitlines()[0]
    assert out.splitlines()[0] == hindi_line, (out.splitlines()[0], hindi_line)   # byte-identical
    assert "\u200b" not in out and "join\u200cer" not in out and "joiner" in out, repr(out)
    assert humanize("👨\u200d👩\u200d👧 trip")["text"] == "👨👩👧 trip\n"           # as before


@test("L20", "humanize: Hindi stock phrases are reported as tells and never rewritten")
def _():
    raw = fixture("draft_hi.txt")
    d = humanize(raw)
    assert d["text"] == raw, "Hindi text was rewritten"
    names = [s["name"] for s in d["report"]["structures"]]
    assert "Hindi stock phrase: आज के इस डिजिटल युग में" in names, names
    assert d["report"]["lexical"] == [], d["report"]["lexical"]


@test("L21", "humanize: a Hindi line is kept after an English deletion elsewhere in the draft")
def _():
    out = humanize(fixture("mixed_delete.txt"))["text"]
    # deleting "Follow for more!" used to drop the whole Hindi line as 'no text left'
    assert out == "Proposals take five hours. Here is the fix.\nबजट हर महीने बनाइए।\n", repr(out)


# ======================================================================
# swipe.py and hooks.json
# ======================================================================
@test("L22", "swipe: Hindi hooks are named by match_hi, counted in words, tagged with lang")
def _():
    _, out, _ = run("ig-viral/swipe.py", os.path.join("hi", "swipe.tsv"), "--json")
    reels = json.loads(out)["reels"]
    row = lambda start: next(r for r in reels if r["hook"].startswith(start))
    nobody = row("कोई आपको")
    assert (nobody["formula_id"], nobody["lang"], nobody["words"]) == (3, "hi", 10), nobody
    assert row("बिना label")["formula_id"] == 2, row("बिना label")
    assert row("आज मैं अपनी")["formula"] == "unclassified", row("आज मैं अपनी")
    assert "lang" not in row("steal this") and row("steal this")["formula_id"] == 9


@test("L23", "hooks.json: every match_hi compiles, and each formula's Hindi example lands on it")
def _():
    sw = module("ig-viral/swipe.py")
    formulas = sw.load_formulas(os.path.join(SK, "ig-reel/hooks.json"))
    assert sum(1 for f in formulas if f[3]) == 25, "expected 25 formulas with match_hi"
    examples = {
        1: "एक गलत investment से मुझे 4 लाख का नुकसान हुआ।", 3: "कोई आपको ये नहीं बताता कि टैक्स कैसे बचता है।",
        5: "पहले invoice बनाने में 3 घंटे लगते थे, अब 20 मिनट।", 7: "लोग जो सबसे बड़ी गलती करते हैं।",
        10: "अगर आप पहली बार gym जा रहे हैं, ये 40 सेकंड देखिए।", 16: "Freelance शुरू करने से पहले कौन से tools चाहिए?",
        19: "Fees भरने से पहले ये एक बात जान लीजिए।", 20: "आपको बड़े budget की ज़रूरत नहीं है।",
        23: "10 में से 7 freelancers ये सवाल नहीं पूछते।", 26: "बचत शुरू करने का सबसे आसान तरीका।",
    }
    for fid, text in examples.items():
        assert sw.classify(text, formulas)[0] == fid, (fid, text, sw.classify(text, formulas))
    for plain in ("मैं कल बाज़ार गया था।", "आज मौसम अच्छा है।"):
        assert sw.classify(plain, formulas) == (None, "unclassified"), plain


@test("L24", "Hindi vocabulary is Devanagari only, so it can never match English text")
def _():
    hs = module("ig-reel/hookscore.py")
    latin = re.compile(r"[A-Za-z]")
    for name in ("HI_SPOKEN_NUMBERS", "HI_MONEY_WORDS", "HI_YOU", "HI_ME", "HI_STAKES", "HI_IMPERATIVES"):
        bad = [w for w in getattr(hs, name) if latin.search(w)]
        assert not bad, (name, bad)
    lex = json.load(open(os.path.join(SK, "ig-human/slop.json"), encoding="utf-8"))
    assert lex["hi"] and all(not latin.search(e["find"]) and e["fix"] for e in lex["hi"]), lex["hi"][:2]


@test("L25", "no invisible characters in any skill source file")
def _():
    import unicodedata
    for s in SCRIPTS + ["ig-reel/hooks.json", "ig-human/slop.json"]:
        src = open(os.path.join(SK, s), encoding="utf-8").read()
        bad = [hex(ord(c)) for c in src if unicodedata.category(c) == "Cf"]
        assert not bad, (s, bad[:5])


# ======================================================================
# Native-review corrections: false positives fixed, natural variants added
# ======================================================================
def formulas():
    sw = module("ig-viral/swipe.py")
    return sw, sw.load_formulas(os.path.join(SK, "ig-reel/hooks.json"))


def hi_slop(text):
    """The Hindi stock phrases detect.py finds in text."""
    d = detect(text)["checks"]["SLOP DENSITY"]
    return d["score"], d["detail"]


def stock(text):
    return [s["name"] for s in humanize(text)["report"]["structures"] if s["name"].startswith("Hindi stock")]


@test("M1", "formula #4: 'locker की जगह ₹500' is not a Replacement; 'की जगह ले ली' still is")
def _():
    sw, F = formulas()
    assert sw.classify("Gym में locker की जगह ₹500 महीने में मिलती है।", F)[0] != 4
    assert sw.classify("₹2,000 के tool ने मेरे editor की जगह ले ली।", F)[0] == 4


@test("M2", "formula #5: 'मुझे डर लगता था' is not Time Collapse; 'पूरा दिन लग जाता था' is")
def _():
    sw, F = formulas()
    assert sw.classify("मुझे डर लगता था कि client पैसे नहीं देगा।", F)[0] != 5
    for hook in ("पहले पूरा दिन लग जाता था।", "Proposal में पाँच घंटे लगते थे।",
                 "पहले invoice बनाने में 3 घंटे लगते थे, अब 20 मिनट।"):
        assert sw.classify(hook, F)[0] == 5, hook


@test("M3", "formula #8: an age is not an Insider Leak; 'मैं 10 साल से…' is")
def _():
    sw, F = formulas()
    for age in ("मैं 25 साल का हूँ और पहली बार gym जा रहा हूँ।", "मैंने 25 साल की उम्र में freelancing शुरू की।"):
        assert sw.classify(age, F)[0] != 8, age
    assert sw.classify("मैं 10 साल से लोगों को train कर रहा हूँ।", F)[0] == 8
    assert sw.classify("मैंने 8 साल freelance projects किए।", F)[0] == 8


@test("M4", "removed slop: सुनिश्चित करें कि, आज के दौर में, क्या आप जानते हैं are no longer flagged")
def _():
    for line in ("Invoice भेजने से पहले सुनिश्चित करें कि rate सही हो।",
                 "आज के दौर में बचत करना आसान नहीं।", "क्या आप जानते हैं कि protein कितना चाहिए?"):
        assert hi_slop(line)[0] == 100.0, (line, hi_slop(line))
        assert stock(line) == [], (line, stock(line))
    finds = {e["find"] for e in json.load(open(os.path.join(SK, "ig-human/slop.json"), encoding="utf-8"))["hi"]}
    assert not finds & {"सुनिश्चित करें कि", "आज के दौर में", "क्या आप जानते हैं", "दोस्तों आज हम बात करेंगे"}


@test("M5", "'दोस्तों आज हम बात करेंगे' is one stock phrase, not two")
def _():
    score, detail = hi_slop("दोस्तों आज हम बात करेंगे बजट पर।")
    assert detail.startswith("1 stock terms"), detail
    assert stock("दोस्तों आज हम बात करेंगे बजट पर।") == ["Hindi stock phrase: आज हम बात करेंगे"]


@test("M6", "commands: चाहिए, लिये, किये, दिये, इसलिए are not; -ें verbs and मत/ज़रूर + -ना are")
def _():
    address = lambda t: hook(t)["checks"]["ADDRESS"]["detail"]
    for t in ("मुझे नए जूते चाहिए।", "ये पैसे मैंने fees के लिये बचाये।", "काम किये बिना पैसा नहीं।",
              "उसने पैसे दिये और चला गया।", "इसलिए client देर से मिला।", "Gym के पहले हफ़्ते की 5 बातें।",
              "रोज़ सुबह उठना आसान नहीं।"):
        assert not address(t).startswith("imperative"), (t, address(t))
    assert address("ये पढ़ें, फिर खरीदें।") == 'imperative ("पढ़ें")'           # shown as written
    assert address("वीडियो ज़रूर देखना।") == 'imperative ("ज़रूर देखना")'
    assert address("ये गलती मत करना।").startswith("imperative")


@test("M7", "caption: 'भेजिए' in a DM or to-me sentence is a DM ask, not a share")
def _():
    assert caption("DM में GUIDE भेजिए")["asks"] == ["DM me"]
    assert caption("मुझे भेज दीजिए")["asks"] == ["DM me"]
    assert caption("अपने भाई को भेज दीजिए।")["asks"] == ["share this"]
    d = caption("इसे save कर लीजिए। अपने दोस्त को भेज दीजिए।")
    assert d["asks"] == ["save this", "share this"], d["asks"]


@test("M8", "stakes: the name राज is not a stake word; रहस्य (secret) is")
def _():
    assert hook("राज ने gym join किया।")["checks"]["STAKES"]["score"] == 20.0
    assert "रहस्य" in hook("Fitness का रहस्य जानिए।")["checks"]["STAKES"]["detail"]


@test("M9", "new slop variants: रील openers and bait, feminine and plural verbs, spelling variants")
def _():
    for line, want in (("आज की इस रील में हम बजट समझेंगे।", "आज की इस रील में"),
                       ("रील को लाइक करें।", "रील को लाइक करें"), ("पोस्ट को लाइक करें।", "पोस्ट को लाइक करें"),
                       ("सही प्लानिंग अहम भूमिका निभाती है।", "अहम भूमिका निभाती है"),
                       ("ये दोनों महत्वपूर्ण भूमिका निभाते हैं।", "महत्वपूर्ण भूमिका निभाते हैं"),
                       ("जैसा कि हम सब जानते हैं, दाम बढ़ रहे हैं।", "जैसा कि हम सब जानते हैं"),
                       ("बजट बनाना अत्यंत महत्त्वपूर्ण है।", "अत्यंत महत्वपूर्ण"),       # त्त्व spelling
                       ("निसंदेह यह सही फैसला है।", "निःसंदेह"),                        # no visarga
                       ("ये कहना गलत नहीं होगा कि दाम बढ़ेंगे।", "यह कहना गलत नहीं होगा"),   # ये for यह
                       ("आज की भाग-दौड़ भरी जिंदगी में।", "आज की भागदौड़ भरी ज़िंदगी में")):  # hyphen, no nukta
        assert f"Hindi stock phrase: {want}" in stock(line), (line, stock(line))


@test("M10", "formulas: 'मत करना' / 'न करें' are Negative Commands; 'X या Y … क्या सही' is Head To Head")
def _():
    sw, F = formulas()
    for t in ("ये गलती मत करना।", "ऐसा न करें।", "Bill भरना मत भूलना।"):
        assert sw.classify(t, F)[0] == 2, (t, sw.classify(t, F))
    assert sw.classify("Gym या yoga, आपके लिए क्या सही है", F)[0] == 17
    assert sw.classify("न समय मिला न पैसा।", F)[0] != 2                      # न…न is not a command


@test("M11", "keyword asks: 'Comment करो GUIDE' and 'GUIDE लिख दो' are typeable keyword asks")
def _():
    for line in ("Comment करो GUIDE", "GUIDE लिख दो", "कमेंट करो GUIDE"):
        d = caption(line)
        assert chk(d, "KEYWORD ASK")["status"] == "PASS" and d["asks"] == ["comment a keyword"], (line, d["asks"])


@test("M12", "spelling fold: the reviewed variants match, and the fold stays narrow")
def _():
    f = module("ig-reel/hookscore.py").deva_fold
    for a, b in (("गये", "गए"), ("लिये", "लिए"), ("किये", "किए"), ("नयी", "नई"), ("यह", "ये"),
                 ("महत्त्व", "महत्व"), ("निःसंदेह", "निसंदेह"), ("भाग-दौड़", "भागदौड़"),
                 ("महत्\u200dवपूर्ण", "महत्वपूर्ण")):
        assert f(a) == f(b), (a, b)
    assert f("ये") == "ये" and f("ये बजट") == "ये बजट"              # the word ये is not turned into ए
    assert f("वह") == "वह" and f("राज") == "राज"
    assert f("Kick-off, café") == "Kick-off, café"                 # English untouched
    assert hook("सोच-समझकर खर्च कीजिए।")["checks"]["LENGTH"]["detail"].startswith("3 words")   # counts unchanged


@test("M13", "numbers: दो as 'give' is not a number; दो लाख, साढ़े, सवा and छः are")
def _():
    spec = lambda t: hook(t)["checks"]["SPECIFICITY"]["detail"]
    for t in ("मुझे वो दो।", "बता दो फिर देखेंगे।", "पैसे दो और जाओ।"):
        assert "दो" not in spec(t), (t, spec(t))
    for t, word in (("दो लाख का नुकसान हुआ।", "दो"), ("साढ़े तीन लाख बचाए।", "साढ़े"),
                    ("सवा लाख की बचत।", "सवा"), ("छः महीने लगे।", "छः")):
        assert word in spec(t), (t, spec(t))
    assert chk(caption("मुझे वो दो।"), "HOOK IS CONCRETE")["status"] == "WARN"
    assert beats("दो लाख बचाए।")["beats"][0]["concrete"] == 2          # दो and लाख
    assert beats("मुझे वो दो।")["beats"][0]["concrete"] == 0


if __name__ == "__main__":
    only = sys.argv[1:]
    passed = failed = 0
    for tid, desc, fn in TESTS:
        if only and not any(tid.startswith(o) for o in only):
            continue
        try:
            fn()
            passed += 1
            print(f"PASS  {tid:<4} {desc}")
        except Exception as e:
            failed += 1
            msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            print(f"FAIL  {tid:<4} {desc}\n            -> {msg[:300]}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

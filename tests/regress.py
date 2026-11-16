#!/usr/bin/env python3
"""Regression suite for the audited bugs.

Every script is run as a subprocess through the .claude/skills symlinks, with
PYTHONDONTWRITEBYTECODE=1 and cwd set to this tests/ folder, so nothing is ever
written inside the skills repository. Run artefacts here are git-ignored.

  python3 regress.py            # all tests
  python3 regress.py H C        # only tests whose id starts with H or C
"""
import json, os, re, subprocess, sys

# The skills under test: $IG_SKILLS_ROOT if set (another checkout of this
# repo), otherwise the repository this tests/ folder lives in.
REPO = os.environ.get("IG_SKILLS_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(REPO, ".claude/skills")
HERE = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
TESTS = []


def test(tid, desc):
    def deco(fn):
        TESTS.append((tid, desc, fn))
        return fn
    return deco


def run(script, *args, stdin=None, cwd=HERE):
    p = subprocess.run([sys.executable, os.path.join(SK, script), *args], input=stdin,
                       capture_output=True, text=True, env=ENV, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def detect(text):
    _, out, _ = run("ig-human/detect.py", "-", "--json", stdin=text)
    return json.loads(out)


def humanize(text):
    _, out, _ = run("ig-human/humanize.py", "-", "--json", stdin=text)
    return json.loads(out)


def caption(text, *extra):
    _, out, _ = run("ig-caption/caption.py", "-", "--json", *extra, stdin=text)
    return json.loads(out)


def chk(d, name):
    return next(c for c in d["checks"] if c["check"] == name)


# ======================================================================
# ig-human / detect.py
# ======================================================================
COMMENT = ("Agree the ones who leave over price were rarely great clients. Mid-project is where "
           "I'd push back: we tried it in 2023 and lost a renewal that was otherwise fine.")


@test("H1a", "detect: short comments get INCONCLUSIVE (no 62 cap, no thin PASS); 4-of-5 is INCONCLUSIVE too")
def _():
    d = detect("I'd push back on mid-project raises. We tried it in 2023 with Northwind and it cost us "
               "a $9,000 renewal that was otherwise fine. Next time I'd wait.")
    assert (d["checks_judged"], d["verdict"], d["human_score"]) == (4, "INCONCLUSIVE", None), d
    d = detect("We raised prices 40% in March 2024 and lost exactly one client, Acme.")
    assert (d["checks_judged"], d["verdict"], d["human_score"]) == (3, "INCONCLUSIVE", None), d


@test("H1b", "detect: unjudgeable checks are reported as n/a, not scored 50")
def _():
    d = detect("We raised prices 40% in March 2024 and lost exactly one client.")
    na = [k for k, v in d["checks"].items() if v["score"] is None]
    assert "BURSTINESS" in na, d["checks"]
    assert all(v["score"] != 50.0 or "too short" not in v["detail"] for v in d["checks"].values())


@test("H1c", "detect: a short comment full of slop is still NOT a pass")
def _():
    d = detect("Great post! It's crucial to leverage these robust, seamless insights.")
    assert d["verdict"] != "PASS", d


@test("H1d", "detect: a short structural tell still drags the verdict")
def _():
    d = detect("It's not just a template, it's a system.")
    assert d["verdict"] != "PASS", d


@test("H1e", "detect: long text is still scored on all five checks and still PASSes")
def _():
    d = detect(open(os.path.join(HERE, "round2_clean.txt")).read())
    assert all(v["score"] is not None for v in d["checks"].values())
    assert d["verdict"] == "PASS"


@test("H2", "detect: short punchy sentences count toward BURSTINESS (were dropped if <=2 words)")
def _():
    t = ("Sent a proposal in 20 minutes this morning. Nobody hunts. It used to take me five hours "
         "every single time a new client asked. Never again. I answer six questions on page one.")
    d = detect(t)
    m = re.search(r"across (\d+) sentences", d["checks"]["BURSTINESS"]["detail"])
    assert m and int(m.group(1)) == 5, d["checks"]["BURSTINESS"]


@test("H2b", "detect: decimals do not split sentences ($18.5k, 3.5 hours)")
def _():
    t = "We billed $18.5k last month. It took 3.5 hours. That was the whole job. Then it stopped."
    d = detect(t)
    m = re.search(r"across (\d+) sentences", d["checks"]["BURSTINESS"]["detail"])
    assert m and int(m.group(1)) == 4, d["checks"]["BURSTINESS"]


@test("H3", "detect: SPECIFICITY counts spoken numbers ('five hours', 'six questions')")
def _():
    t = ("Proposals used to take me five hours. Now it takes twenty minutes because I answer the six "
         "questions every buyer asks before they sign, and I do it on page one of the doc.")
    d = detect(t)
    m = re.match(r"(\d+) concrete", d["checks"]["SPECIFICITY"]["detail"])
    assert m and int(m.group(1)) >= 3, d["checks"]["SPECIFICITY"]


@test("H4", "detect: slop words inside a URL are not counted")
def _():
    d = detect(open(os.path.join(HERE, "url.txt")).read())
    assert d["checks"]["SLOP DENSITY"]["score"] == 100.0, d["checks"]["SLOP DENSITY"]


# ======================================================================
# ig-human / humanize.py
# ======================================================================
@test("H5a", "humanize: 'Follow for more and tag someone who needs this!' leaves nothing, not 'And!'")
def _():
    out = humanize("Follow for more and tag someone who needs this!\n")["text"].strip()
    assert out == "", repr(out)


@test("H5b", "humanize: 'Save this, and follow for more.' -> 'Save this.'")
def _():
    out = humanize("Save this, and follow for more.\n")["text"].strip()
    assert out == "Save this.", repr(out)


@test("H5c", "humanize: 'Tag someone who needs this 👇' leaves no orphan emoji line")
def _():
    out = humanize("Great tip on pricing.\nTag someone who needs this 👇\n")["text"].strip()
    assert out == "Great tip on pricing.", repr(out)


@test("H5d", "humanize: mid-paragraph bait sentence removed cleanly")
def _():
    out = humanize("Follow for more and tag someone who needs this! Full guide at "
                   "https://example.com/delve-guide, link in bio.\n")["text"].strip()
    assert out == "Full guide at https://example.com/delve-guide, link in bio.", repr(out)


@test("H5e", "humanize: legit conjunctions and emoji lines are untouched")
def _():
    src = "I think so.\nSalt and pepper.\nRock or paper?\n🔥\nWe ship, and we ship fast.\n"
    out = humanize(src)["text"]
    assert out == src, repr(out)


@test("H5f", "humanize: cleanup after a deletion leaves the writer's own 'so'/'and' alone")
def _():
    out = humanize("Follow for more. I think so. Salt and pepper. We ship, and we ship fast.\n")["text"].strip()
    assert out == "I think so. Salt and pepper. We ship, and we ship fast.", repr(out)


@test("H6a", "slop.json: exactly 5 hashtags (Instagram's cap) is not a hashtag wall")
def _():
    r = humanize("Quick note on pricing.\n#a #b #c #d #e\n")["report"]["structures"]
    assert not any("ashtag" in s["name"] for s in r), r


@test("H6b", "slop.json: 6+ hashtags is flagged, with Instagram advice (no 'LinkedIn')")
def _():
    r = humanize("Quick note on pricing.\n#a #b #c #d #e #f\n")["report"]["structures"]
    wall = [s for s in r if "ashtag" in s["name"]]
    assert wall and "linkedin" not in wall[0]["fix"].lower() and "five" in wall[0]["fix"].lower(), r
    assert "linkedin" not in open(os.path.join(SK, "ig-human/slop.json")).read().lower()


@test("H7", "humanize: 'Run, don't walk,' with commas is caught")
def _():
    out = humanize("Run, don't walk, to grab the template.\n")["text"].strip()
    assert out == "To grab the template.", repr(out)


@test("H8a", "humanize: inline staged reveal 'The result? We cut...' is flagged")
def _():
    r = humanize("We tried it for a month. The result? We cut proposal time to 20 minutes.\n")
    assert any("rhetorical" in s["name"].lower() for s in r["report"]["structures"]), r["report"]


@test("H8b", "humanize: fragment triad 'Clarity. Speed. Confidence.' is flagged")
def _():
    r = humanize("Here is what changed.\nClarity. Speed. Confidence.\n")
    assert any("three" in s["name"].lower() for s in r["report"]["structures"]), r["report"]


@test("H9", "regression: original sloppy draft still cleaned (19 artefacts, URL intact, no Cf)")
def _():
    src = open(os.path.join(HERE, "draft.txt"), encoding="utf-8").read()
    r = humanize(src)
    n = sum(h["count"] for k in ("invisible", "typographic", "lexical") for h in r["report"][k])
    t = r["text"]
    assert n == 19, n
    assert "https://example.com/delve-guide" in t and "—" not in t and "​" not in t
    assert "And!" not in t


# ======================================================================
# ig-caption / caption.py
# ======================================================================
@test("C1a", "caption: 'Comment CONTRACT' is a keyword ask")
def _():
    assert caption("Comment CONTRACT and I will send it.\n")["asks"] == ["comment a keyword"]


@test("C1b", "caption: 'Comment \"the contract guide\"' is NOT a valid keyword ask, and is warned")
def _():
    d = caption('Comment "the contract guide" below.\n')
    assert "comment a keyword" not in d["asks"], d["asks"]
    assert chk(d, "KEYWORD ASK")["status"] == "WARN"


@test("C1c", "caption: lower-case 'comment contract below' and 'Comment 📄' are warned")
def _():
    for t in ("comment contract below\n", "Comment 📄 for the guide.\n"):
        d = caption(t)
        assert "comment a keyword" not in d["asks"] and chk(d, "KEYWORD ASK")["status"] == "WARN", (t, d)


@test("C1d", "caption: 'comment below if...' is not mistaken for a keyword ask")
def _():
    d = caption("Comment below if you have been burned by a late approval.\n")
    assert not any(c["check"] == "KEYWORD ASK" for c in d["checks"]), d["checks"]


@test("C2", "caption: greeting or emoji as first character FAILs FIRST LINE")
def _():
    for t in ("Hey guys! Quick one about pricing today.\n", "🔥 Five hours to 20 minutes.\n",
              "Good morning fam ☀️ hope you are well\n"):
        assert chk(caption(t), "FIRST LINE")["status"] == "FAIL", t
    assert chk(caption("Proposals used to eat my whole Tuesday.\n"), "FIRST LINE")["status"] == "PASS"


@test("C3", "caption: sentence-initial words are not counted as names in HOOK IS CONCRETE")
def _():
    d = caption("Hey guys! Quick one about pricing today.\n")
    assert chk(d, "HOOK IS CONCRETE")["status"] == "WARN", chk(d, "HOOK IS CONCRETE")
    d = caption("Proposals used to eat my whole Tuesday.\n")
    assert chk(d, "HOOK IS CONCRETE")["status"] == "PASS"


@test("C4", "regression: fixed caption still READY, bad caption still FIX")
def _():
    rc, out, _ = run("ig-caption/caption.py", os.path.join(HERE, "cap_fixed.txt"),
                     "--keywords", "client proposals,proposal template")
    assert rc == 0 and "VERDICT  READY" in out, out
    d = json.loads(run("ig-caption/caption.py", os.path.join(HERE, "cap_bad.txt"), "--json")[1])
    assert d["verdict"] == "FIX" and len(d["asks"]) == 3


# ======================================================================
# ig-reel / hookscore.py + beats.py
# ======================================================================
@test("R1", "hookscore: exit codes documented in --help (exit 1 is a verdict, not a crash)")
def _():
    rc, out, _ = run("ig-reel/hookscore.py", "--help")
    assert rc == 0 and re.search(r"exit", out, re.I) and "verdict" in out.lower(), out


@test("R2", "beats: spoken numbers count as concrete ('five hours' is a number)")
def _():
    a = json.loads(run("ig-reel/beats.py", os.path.join(HERE, "script.txt"), "--json")[1])
    assert a["beats"][0]["concrete"] > 0, a["beats"][0]
    assert not any("Beat 1 has no number" in n for n in a["notes"]), a["notes"]


@test("R3", "beats: filler like 'about' is not reported as a loop")
def _():
    s = ("Hey guys welcome back to the channel today we are going to talk about something really important\n"
         "It is about how you think about things\nAnd why it matters for you\n"
         "Because it really does matter a lot\nSo think about it\n")
    a = json.loads(run("ig-reel/beats.py", "-", "--json", stdin=s)[1])
    assert any(n.startswith("No loop") for n in a["notes"]), a["notes"]
    a = json.loads(run("ig-reel/beats.py", os.path.join(HERE, "script.txt"), "--json")[1])
    assert any('"five, hours"' in n for n in a["notes"]), a["notes"]   # real loop still found


@test("R4", "ig-reel/SKILL.md example reproduces with hookscore.py")
def _():
    md = open(os.path.join(SK, "ig-reel/SKILL.md"), encoding="utf-8").read()
    block = md.split("HOOKS  (scored)")[1].split("```")[0]
    rows = re.findall(r"^\s+(\d+)\s+(STRONG|OK|WEAK)\s+#\d+\s+.+?\"(.+)\"\s*$", block, re.M)
    assert len(rows) == 3, block
    for score, verdict, hook in rows:
        d = json.loads(run("ig-reel/hookscore.py", "--hook", hook, "--json")[1])
        assert round(d["score"]) == int(score) and d["verdict"] == verdict, (hook, d["score"], d["verdict"], score, verdict)


@test("R5", "regression: README hook ranking still 85.6 / 81.4 / 54.4 / 9.6")
def _():
    d = json.loads(run("ig-reel/hookscore.py", os.path.join(HERE, "readme_hooks.txt"), "--json")[1])
    assert [x["score"] for x in d] == [85.6, 81.4, 54.4, 9.6], [x["score"] for x in d]


@test("R6", "beats does not create __pycache__ in the repo even without PYTHONDONTWRITEBYTECODE")
def _():
    env = {k: v for k, v in ENV.items() if k != "PYTHONDONTWRITEBYTECODE"}
    subprocess.run([sys.executable, os.path.join(SK, "ig-reel/beats.py"), os.path.join(HERE, "script.txt")],
                   capture_output=True, env=env, cwd=HERE)
    assert not os.path.exists(os.path.join(REPO, "skills/ig-reel/__pycache__"))


# ======================================================================
# ig-viral / swipe.py
# ======================================================================
@test("V1", "swipe: --out with a bare filename writes the file instead of crashing")
def _():
    p = os.path.join(HERE, "swipe_local.md")
    if os.path.exists(p):
        os.remove(p)
    rc, _, err = run("ig-viral/swipe.py", "captured.tsv", "--out", "swipe_local.md")
    assert rc == 0 and os.path.exists(p), err


@test("V2", "swipe: length, cta and on-screen columns are used in the top/bottom comparison")
def _():
    rc, out, _ = run("ig-viral/swipe.py", "captured.tsv")
    assert re.search(r"median length:\s+top [\d.]+s\s+vs bottom [\d.]+s", out), out
    assert re.search(r"cta, top third:", out) and re.search(r"on-screen card:", out), out
    d = json.loads(run("ig-viral/swipe.py", "captured.tsv", "--json")[1])
    assert d["top_length"] is not None and d["top_ctas"], d.keys()


@test("V3", "yt-dlp documented as an optional install (SKILL.md + README)")
def _():
    for f in ("skills/ig-viral/SKILL.md", "README.md"):
        t = open(os.path.join(REPO, f), encoding="utf-8").read()
        assert re.search(r"pip install yt-dlp", t), f


@test("V4", "regression: swipe ranking unchanged; files without the new columns still work")
def _():
    d = json.loads(run("ig-viral/swipe.py", "captured.tsv", "--json")[1])
    assert [r["outlier"] for r in d["reels"]][:3] == [60.0, 37.45, 22.86], [r["outlier"] for r in d["reels"]][:3]
    rc, out, _ = run("ig-viral/swipe.py", "-", stdin="@a\t48000\t412000\tnobody tells you your first 30 reels flop\n")
    assert rc == 0 and "baseline: follower count" in out and "median length" not in out, out


# ======================================================================
# Round 2: the five issues found in the final review
# ======================================================================
def paragraphs(path):
    return [re.sub(r"\s+", " ", p).strip() for p in
            re.split(r"\n\s*\n", open(os.path.join(REPO, path), encoding="utf-8").read())]


@test("F1", "README: 'Changing the shape...' sentence is back in the flagged-instead-of-fixed paragraph")
def _():
    ps = paragraphs("README.md")
    flagged = [p for p in ps if p.startswith("**What gets flagged instead of fixed:**")]
    assert len(flagged) == 1, flagged
    assert flagged[0].endswith("Changing the shape of a sentence needs judgement, so those come back "
                               "for a rewrite rather than getting mangled by a regex."), flagged[0][-160:]
    short = [p for p in ps if p.startswith("Short drafts (comments, DMs")]
    assert len(short) == 1 and "Changing the shape" not in short[0] \
        and short[0].endswith("still come back REVIEW or FLAGGED."), short


@test("F2a", "humanize: writer's own 'And?' line survives a deletion elsewhere")
def _():
    out = humanize("We raised prices.\nAnd?\nNothing happened. Follow for more.\n")["text"]
    assert out == "We raised prices.\nAnd?\nNothing happened.\n", repr(out)


@test("F2b", "humanize: writer's own 'But.' (own line and mid-paragraph) survives a deletion elsewhere")
def _():
    out = humanize("I could have quit.\nBut.\nI did not. But. I almost did. Tag someone who needs this.\n")["text"]
    assert out == "I could have quit.\nBut.\nI did not. But. I almost did.\n", repr(out)


@test("F2c", "humanize: conjunctions orphaned BY a deletion are still removed (H5a/b/d cases)")
def _():
    for src, want in (("Follow for more and tag someone who needs this!\n", ""),
                      ("Save this, and follow for more.\n", "Save this."),
                      ("And? Follow for more and tag someone who needs this! Done.\n", "And? Done.")):
        out = humanize(src)["text"].strip()
        assert out == want, (src, out)


@test("F2d", "humanize: protected sentences never leak placeholders or double punctuation")
def _():
    cases = {"Cats, or? Dogs, and. Follow for more.\n": "Cats, or? Dogs, and.",
             "And? https://x.com/leverage Follow for more.\n": "And? https://x.com/leverage.",
             "We raised prices. But. Tag someone who needs this.\n": "We raised prices. But."}
    for src, want in cases.items():
        out = humanize(src)["text"]
        assert "\x00" not in out and out.strip() == want, (src, out)


@test("F3a", "caption: 'Hi-res ...' and 'Welcome to ...' first lines are not greetings")
def _():
    for t in ("Hi-res proof: we closed 4 of 5.\n", "Welcome to the only proposal template you need.\n",
              "Hiring a designer cost me $9,000.\n", "Yours truly lost $18,000 on one clause.\n",
              "Superfans are built in the DMs.\n"):
        assert chk(caption(t), "FIRST LINE")["status"] != "FAIL", (t, chk(caption(t), "FIRST LINE"))


@test("F3b", "caption: real greetings still FAIL")
def _():
    for t in ("Hey guys! Quick one about pricing today.\n", "Hi, quick one on pricing.\n",
              "Hi there, welcome to my page.\n", "Hello everyone 👋\n", "Welcome back to the channel.\n",
              "Good morning fam ☀️ hope you are well\n", "Happy Monday! New template today.\n",
              "What's up everyone, quick tip.\n"):
        assert chk(caption(t), "FIRST LINE")["status"] == "FAIL", t


@test("F4", "swipe: m:ss and h:mm:ss lengths are parsed as seconds")
def _():
    tsv = ("account\tmedian\tviews\thook\tlength\n"
           "@a\t1000\t9000\tnobody tells you this\t0:24\n"
           "@b\t1000\t500\tso today I wanted to talk\t1:05\n"
           "@c\t1000\t3000\tsteal this template it took two years\t31s\n"
           "@d\t1000\t800\there is my long video\t1:02:03\n")
    d = json.loads(run("ig-viral/swipe.py", "-", "--json", stdin=tsv)[1])
    got = {r["account"]: r["length_s"] for r in d["reels"]}
    assert got == {"@a": 24.0, "@b": 65.0, "@c": 31.0, "@d": 3723.0}, got
    out = run("ig-viral/swipe.py", "-", stdin=tsv)[1]
    assert "median length:         top 24s  vs bottom 65s" in out, out


@test("F5", "beats: runs on its own (no hookscore.py beside it) and still counts spoken numbers")
def _():
    solo = os.path.join(HERE, "solo_beats")
    os.makedirs(solo, exist_ok=True)
    for f in os.listdir(solo):
        os.remove(os.path.join(solo, f))
    import shutil
    shutil.copy(os.path.join(SK, "ig-reel/beats.py"), solo)
    p = subprocess.run([sys.executable, os.path.join(solo, "beats.py"), os.path.join(HERE, "script.txt"), "--json"],
                       capture_output=True, text=True, env=ENV, cwd=HERE)
    assert p.returncode == 0, p.stderr[-300:]
    a = json.loads(p.stdout)
    assert a["beats"][0]["concrete"] > 0, a["beats"][0]
    # the fallback list must match hookscore's, so the two modes never disagree
    import importlib.util
    spec = importlib.util.spec_from_file_location("hs", os.path.join(SK, "ig-reel/hookscore.py"))
    sys.dont_write_bytecode = True
    hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
    spec2 = importlib.util.spec_from_file_location("bt", os.path.join(solo, "beats.py"))
    bt = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(bt)
    assert bt.SPOKEN_NUMBERS == hs.SPOKEN_NUMBERS and bt.MONEY_WORDS == hs.MONEY_WORDS



# ======================================================================
# Round 3: INCONCLUSIVE verdict, lexicon matching, URL masking
# ======================================================================
def detect_rc(text, *extra):
    rc, out, err = run("ig-human/detect.py", "-", *extra, stdin=text)
    return rc, out


@test("I1", "detect: 'Ok.' is INCONCLUSIVE with no score, exit 3 (was 100.0 PASS on 3 of 5 checks)")
def _():
    d = detect("Ok.")
    assert d["verdict"] == "INCONCLUSIVE" and d["human_score"] is None and d["checks_judged"] == 3, d
    rc, _ = detect_rc("Ok.")
    assert rc == 3, rc


@test("I2", "detect: generic short marketing line is INCONCLUSIVE, not PASS")
def _():
    d = detect("This is a great opportunity to grow your business today.")
    assert d["verdict"] == "INCONCLUSIVE", d


@test("I3", "detect: a measured failure on a short text is still reported (FLAGGED), with a partial score")
def _():
    d = detect("Unlock your potential with our innovative solution for modern teams.")
    assert d["verdict"] == "FLAGGED" and d["human_score"] is not None and d["complete"] is False, d
    rc, _ = detect_rc("Unlock your potential with our innovative solution for modern teams.")
    assert rc == 1


@test("I4", "detect: a structural tell in a one-liner is reported, not hidden behind INCONCLUSIVE")
def _():
    d = detect("It's not just a template, it's a system.")
    assert d["verdict"] in ("REVIEW", "FLAGGED"), d


@test("I5", "detect: PASS is impossible under 25 words or with <4 checks, over a spread of clean short texts")
def _():
    for t in ("Thanks Lena, appreciate you.", "Sam, sent. Check your DMs.", "Nobody hunts.",
              "Sent a proposal in 20 minutes this morning.", "Five hours to twenty minutes.",
              "Freelancers and small agencies: send the proposal the same day.",
              "We cut it from 5 hours to 20 minutes. It works. Try it. Seriously."):
        d = detect(t)
        assert d["verdict"] == "INCONCLUSIVE" and d["human_score"] is None, (t, d["verdict"], d["checks_judged"])


@test("I6", "detect: full-length texts unchanged (rewritten draft 97.3 PASS, sloppy draft FLAGGED)")
def _():
    d = detect(open(os.path.join(HERE, "round2_clean.txt")).read())
    assert (d["human_score"], d["verdict"], d["checks_judged"], d["complete"]) == (97.3, "PASS", 5, True), d
    assert detect(open(os.path.join(HERE, "draft.txt"), encoding="utf-8").read())["verdict"] == "FLAGGED"


@test("I7", "detect: text output says INCONCLUSIVE and why; compare mode copes with a missing score")
def _():
    rc, out = detect_rc("Ok.")
    assert "INCONCLUSIVE" in out and "judged on 3 of 5" in out and "n/a" in out, out
    p = os.path.join(HERE, "ok.txt"); open(p, "w").write("Ok.\n")
    rc, out, err = run("ig-human/detect.py", os.path.join(HERE, "draft.txt"), p)
    assert "Traceback" not in err and "FLAGGED  ->  n/a INCONCLUSIVE" in out, (out[-300:], err[-300:])


@test("I8", "lexicon: every one of the 154 entries matches itself in detect AND humanize")
def _():
    lex = json.load(open(os.path.join(SK, "ig-human/slop.json"), encoding="utf-8"))
    miss_d, miss_h = [], []
    for e in lex["words"] + lex["phrases"]:
        f = e["find"]
        if "stock terms" not in detect(f"I said {f} today, honestly, about the plan.")["checks"]["SLOP DENSITY"]["detail"] \
                or detect(f"I said {f} today, honestly, about the plan.")["checks"]["SLOP DENSITY"]["detail"].startswith("0 "):
            miss_d.append(f)
    # humanize: one subprocess for the whole lexicon, one entry per line
    src = "\n".join(f"x {e['find']} y" for e in lex["words"] + lex["phrases"]) + "\n"
    hits = {h["find"] for h in humanize(src)["report"]["lexical"]}
    miss_h = [e["find"] for e in lex["words"] + lex["phrases"] if e["find"] not in hits]
    assert not miss_d and not miss_h, (miss_d, miss_h)


@test("I9", "lexicon: 'What are your thoughts?' is caught (never matched before)")
def _():
    assert detect("What are your thoughts?")["checks"]["SLOP DENSITY"]["detail"].startswith("1 ")
    assert humanize("Great question. What are your thoughts?\n")["report"]["lexical"], "humanize missed it"


@test("I10", "detect: curly apostrophes match lexicon entries (\"In today’s fast-paced world\")")
def _():
    assert detect("In today’s fast-paced world, we ship.")["checks"]["SLOP DENSITY"]["detail"].startswith("1 ")


@test("I11", "detect: URLs, www. links and emails are masked from slop; slop outside them still counts")
def _():
    for t, n in (("Read it at https://example.com/leverage-robust-seamless-guide.", 0),
                 ("Read it at www.leverage-hub.com/robust today.", 0),
                 ("Email leverage@robust-seamless.com for it.", 0),
                 ("We leverage it. See https://example.com/robust for the rest.", 1),
                 ("A robust plan (https://example.com/seamless).", 1)):
        det = detect(t)["checks"]["SLOP DENSITY"]["detail"]
        assert det.startswith(f"{n} "), (t, det)


@test("I12", "short comments, DMs, replies and bios from the functional tests: never PASS on <4 checks")
def _():
    sys.path.insert(0, HERE)
    import outputs as o
    texts = [c for _, c in o.COMMENTS] + list(o.REPLIES.values()) + [o.DM_KEYWORD] \
        + [m for _, m in o.DM_FOLLOWUPS] + [o.PROFILE_REWRITES["bio"]] + [f["says"] for f in o.STORY]
    seen = {}
    for t in texts:
        d = detect(t)
        seen[d["verdict"]] = seen.get(d["verdict"], 0) + 1
        assert not (d["verdict"] == "PASS" and d["checks_judged"] < 4), (t, d)
        assert d["verdict"] != "INCONCLUSIVE" or d["human_score"] is None
    assert seen.get("INCONCLUSIVE"), seen



# ======================================================================
# Round 4: all-five rule, URL word-count loophole
# ======================================================================
def spec_words(d):
    import re as _re
    m = _re.search(r"n/a: (\d+) words", d["checks"]["SPECIFICITY"]["detail"])
    return int(m.group(1)) if m else None


@test("J1", "all-five rule: the +10-day DM (27 words, 3 sentences) is INCONCLUSIVE, not 77.0 PASS")
def _():
    sys.path.insert(0, HERE)
    import outputs as o
    d = detect(o.DM_FOLLOWUPS[1][1])
    assert (d["verdict"], d["human_score"], d["complete"]) == ("INCONCLUSIVE", None, False), d
    assert d["checks"]["BURSTINESS"]["score"] is None


@test("J2", "url.txt (24 visible words + a URL) is INCONCLUSIVE and counted as 21 words, not 30")
def _():
    d = detect(open(os.path.join(HERE, "url.txt")).read())
    assert d["verdict"] == "INCONCLUSIVE" and spec_words(d) == 21, (d["verdict"], d["checks"]["SPECIFICITY"])


@test("J3", "URLs, www. links and emails add nothing to the word count used for the 25-word minimum")
def _():
    base = "We rebuilt the proposal template last quarter and it now closes four of every five deals we send out"
    n = spec_words(detect(base + "."))
    # The link is the only difference: no extra real words come with it.
    for extra in (" (https://example.com/a/very/long/path/with/many/words/in/it/for/sure/ok)",
                  " (www.example.com/one/two/three/four/five/six/seven/eight/nine)",
                  " (hello.team.members.here@dana-proposal-studio.example.com)"):
        d = detect(base + extra + ".")
        assert spec_words(d) == n, (extra, spec_words(d), n)


@test("J4", "full stops inside a URL do not create sentences")
def _():
    d = detect("See https://a.example.com/x.y.z for it. We ship. It works. Done today.")
    assert "across 4 sentences" in d["checks"]["BURSTINESS"]["detail"], d["checks"]["BURSTINESS"]


@test("J5", "all-five rule: a measured failure on a partial panel is still REVIEW/FLAGGED with a score")
def _():
    sys.path.insert(0, HERE)
    from corpus import corpus
    c = corpus()
    d = detect(c["run-on 1 sentence"])
    assert d["verdict"] == "FLAGGED" and d["human_score"] is not None and not d["complete"], d
    d = detect(c["comment #3"])
    assert d["verdict"] == "REVIEW" and d["human_score"] is not None and not d["complete"], d


@test("J6", "no full-length (5/5) text changed verdict; no PASS anywhere without all five checks")
def _():
    sys.path.insert(0, HERE)
    from corpus import corpus
    before = json.load(open(os.path.join(HERE, "verdicts_before.json")))
    changed = []
    for name, text in corpus().items():
        d = detect(text)
        assert d["verdict"] != "PASS" or d["complete"], (name, d)
        b = before[name]
        if b["complete"] and (d["verdict"], d["human_score"]) != (b["verdict"], b["human_score"]) \
                and "http" not in text and "@" not in text.replace("@dana", ""):
            changed.append((name, b["verdict"], b["human_score"], d["verdict"], d["human_score"]))
    assert not changed, changed


@test("J7", "the two full-length verdict changes are exactly the URL fix: real sentence counts, slop/fingerprint unchanged")
def _():
    sys.path.insert(0, HERE)
    from corpus import corpus
    c = corpus()
    from dm_fills import OLD
    c["DM keyword (old fill)"] = OLD
    for name, sents, verdict in (("DM keyword (old fill)", 4, "FLAGGED"), ("cap_bad.txt", 5, "REVIEW")):
        d = detect(c[name])
        assert f"across {sents} sentences" in d["checks"]["BURSTINESS"]["detail"], (name, d["checks"]["BURSTINESS"])
        assert d["verdict"] == verdict and d["complete"], (name, d["verdict"])
        assert d["checks"]["FINGERPRINT"]["score"] == 100.0



# ======================================================================
# Round 5: the /ig-dm keyword-delivery template against its own detector
# ======================================================================
def dm_section():
    md = open(os.path.join(SK, "ig-dm/SKILL.md"), encoding="utf-8").read()
    return md.split("## The keyword delivery")[1].split("## The first message")[0]


def dm_blocks():
    return re.findall(r"```\n(.*?)\n```", dm_section(), re.S)


@test("K1", "ig-dm: the worked keyword DM in SKILL.md is PASS on all five checks, nothing to strip or flag")
def _():
    blocks = dm_blocks()
    assert len(blocks) == 2, blocks
    example = blocks[1] + "\n"
    d = detect(example)
    assert d["verdict"] == "PASS" and d["complete"], (d["human_score"], d["verdict"], d["checks"])
    h = humanize(example)["report"]
    assert not any(h[k] for k in ("invisible", "typographic", "lexical", "structures")), h
    lines = [l for l in example.splitlines() if l.strip()]
    assert len(lines) == 3 and "https://" in lines[0] and lines[2].endswith("?"), lines   # thing first, no gate
    assert len(lines[2].split()) <= 6, lines[2]                                          # answerable fast
    assert len(example.split()) <= 50, len(example.split())                              # still a short DM


@test("K2", "ig-dm: the template filled across four niches is never FLAGGED (all PASS on five checks)")
def _():
    sys.path.insert(0, HERE)
    from dm_fills import NEW
    for name, text in NEW.items():
        d = detect(text)
        assert d["verdict"] == "PASS" and d["complete"], (name, d["human_score"], d["verdict"])
        lines = [l for l in text.splitlines() if l.strip()]
        assert len(lines) == 3 and "http" in lines[0] and lines[2].endswith("?"), (name, lines)


@test("K3", "ig-dm: the template asks for short-long-short and the old even-length fill is still FLAGGED")
def _():
    tpl = dm_blocks()[0]
    assert "where to start, in a few words" in tpl and "one longer sentence" in tpl, tpl
    assert "short, long, short" in dm_section()
    sys.path.insert(0, HERE)
    from dm_fills import OLD
    d = detect(OLD)
    assert (d["human_score"], d["verdict"]) == (47.4, "FLAGGED"), d    # same detector, same verdict


@test("K4", "detector thresholds untouched: PASS 70/55, REVIEW 50, all five checks required")
def _():
    src = open(os.path.join(SK, "ig-human/detect.py"), encoding="utf-8").read()
    for s in ('verdict = "PASS" if overall >= 70 and min(scores) >= 55 else (',
              '"REVIEW" if overall >= 50 else "FLAGGED")',
              'if verdict == "PASS" and len(scores) < len(CHECKS):',
              "MIN_SENTENCES = 4", "MIN_WORDS = 25",
              "score = scale(cv, human=0.70, machine=0.22)",
              "score = scale(density, human=6.0, machine=0.5)"):
        assert s in src, s


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

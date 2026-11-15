#!/usr/bin/env python3
"""Phase 2 tests: research archive, production packages, carousel rendering and
the content calendar. Same harness as regress.py; every run uses a fresh
temporary archive, so no real research data is read or written.

  python3 phase2.py            # all tests
  python3 phase2.py P1 P9      # only ids starting with P1 or P9
"""
import json, os, shutil, subprocess, sys, tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regress import ENV, HERE, SK, run  # noqa: E402

TESTS = []
DAY = "2026-11-15"


def test(tid, desc):
    def deco(fn):
        TESTS.append((tid, desc, fn))
        return fn
    return deco


class Archive:
    """A throwaway research archive."""
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="ig_research_")
        self.r("init")

    def r(self, *args, ok=True):
        rc, out, err = run("ig-viral/research.py", "--data", self.dir, "--today", DAY, *args)
        if ok:
            assert rc == 0, (args, rc, err)
        return rc, out, err

    def c(self, *args):
        return run("ig-plan/content_calendar.py", "--data", self.dir, "--today", DAY, *args)

    def post(self, **fields):
        fields.setdefault("format", "reel")
        return self.r("post", "add", "--json", json.dumps(fields, ensure_ascii=False), ok=False)

    def load(self, name):
        return [json.loads(l) for l in open(os.path.join(self.dir, name), encoding="utf-8") if l.strip()]

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def with_archive(fn):
    def wrapped():
        a = Archive()
        try:
            fn(a)
        finally:
            a.close()
    return wrapped


def idea(a, title, fmt="reel", insights="", rel=4, orig=4, val=4, conf=4, eff=2, extra=()):
    args = ["idea", "add", "--title", title, "--format", fmt, "--relevance", str(rel), "--originality", str(orig),
            "--value", str(val), "--confidence", str(conf), "--effort", str(eff), *extra]
    if insights:
        args += ["--insights", insights]
    return a.r(*args, ok=False)


# ======================================================================
# research.py: registry and discovery
# ======================================================================
@test("P1", "registry holds 25+ accounts, lists the ones due for research, upserts on import")
@with_archive
def _(a):
    for i in range(1, 28):
        a.r("account", "add", "--handle", f"acct{i}", "--name", f"Account {i}", "--niche", "finance",
            "--why", "test", "--priority", "high" if i < 5 else "medium")
    _, out, _ = a.r("account", "list")
    assert "27 account(s)" in out, out
    a.r("account", "done", "@acct1", "--on", "2026-11-10")
    a.r("account", "done", "@acct2", "--on", "2026-10-01")
    _, out, _ = a.r("account", "list", "--due", "14", "--json")
    due = [x["handle"] for x in json.loads(out)]
    assert "@acct1" not in due and "@acct2" in due and len(due) == 26, due
    assert due[:3] == ["@acct3", "@acct4", "@acct2"], due   # high priority first; never researched before stale
    tsv = os.path.join(a.dir, "in.tsv")
    open(tsv, "w").write("handle\tname\tniche\twhy\tpriority\n@acct1\tRenamed\tfinance\tx\tlow\n@new\tNew\tdesign\ty\thigh\n")
    _, out, _ = a.r("account", "import", tsv)
    assert "1 new, 1 updated" in out, out


@test("P2", "registry refuses a bad priority, a baseline with no basis, and text that is not a handle")
@with_archive
def _(a):
    rc, _, err = a.r("account", "add", "--handle", "(handle unknown)", ok=False)
    assert rc == 1 and "not an Instagram handle" in err, err
    tsv = os.path.join(a.dir, "in.tsv")
    open(tsv, "w").write("handle\tname\n@real_one\tA\n(handle unknown)\tB\n(handle unknown)\tC\n")
    _, out, _ = a.r("account", "import", tsv)
    assert "1 new" in out and "skipped 2 row(s)" in out and "row 3:" in out and "row 4:" in out, out
    rc, _, err = a.r("account", "add", "--handle", "@x", "--priority", "urgent", ok=False)
    assert rc == 1 and "priority" in err, err
    rc, _, err = a.r("account", "add", "--handle", "@x", "--baseline-views", "50000", ok=False)
    assert rc == 1 and "baseline_basis" in err, err
    a.r("account", "add", "--handle", "@x", "--baseline-views", "50,000", "--baseline-basis", "observed")


@test("P3", "discovery: candidates are not researched until promoted; rejecting keeps them out")
@with_archive
def _(a):
    a.r("discover", "add", "--handle", "instagram.com/newcreator", "--why", "carousel style", "--found-via", "web search")
    _, out, _ = a.r("discover", "list")
    assert "@newcreator" in out and "instagram.com" not in out, out
    _, out, _ = a.r("account", "list", "--due", "0", "--json")
    assert json.loads(out) == [], out
    _, out, _ = a.r("discover", "add", "--handle", "@newcreator", "--why", "again", "--found-via", "x")
    assert "already in the registry" in out, out
    a.r("discover", "promote", "@newcreator")
    _, out, _ = a.r("account", "list", "--due", "0", "--json")
    assert [x["handle"] for x in json.loads(out)] == ["@newcreator"], out
    a.r("discover", "add", "--handle", "@spam", "--why", "x", "--found-via", "x")
    a.r("discover", "reject", "@spam")
    _, out, _ = a.r("account", "list", "--status", "rejected", "--json")
    assert [x["handle"] for x in json.loads(out)] == ["@spam"]


# ======================================================================
# research.py: posts, outliers, search, trends
# ======================================================================
@test("P4", "posts: a number with no basis is refused; estimates are kept but never ranked")
@with_archive
def _(a):
    rc, _, err = a.post(handle="@x", url="u0", hook="Stop doing this", views="41000")
    assert rc == 1 and "no basis" in err, err
    rc, _, err = a.post(handle="@x", url="u0", hook="Stop doing this", views="lots", views_basis="observed")
    assert rc == 1 and "not a number" in err, err
    assert a.load("posts.jsonl") == []                       # nothing written on refusal
    rc, out, _ = a.post(handle="@x", url="u1", hook="Stop doing this", views="900000", views_basis="estimate")
    assert rc == 0 and "not in the registry" in out, out
    for i, v in enumerate((10000, 12000, 11000, 30000)):
        a.post(handle="@x", url=f"o{i}", hook="Nobody tells you this", views=str(v), views_basis="observed")
    _, out, _ = a.r("outliers", "--min", "2")
    assert "p-0005" in out and "p-0001" not in out, out      # 30k vs median 11.5k; the estimate is ignored
    assert "2.6x" in out, out


@test("P5", "posts: TSV import, de-duplication by URL, Hindi hooks tagged and searchable")
@with_archive
def _(a):
    tsv = os.path.join(a.dir, "posts.tsv")
    open(tsv, "w", encoding="utf-8").write(
        "account\turl\tformat\ttopic\thook\tviews\tviews_basis\tcategory\taudience_questions\n"
        "@x\tu1\treel\tbudget\tकोई आपको ये नहीं बताता कि बचत कैसे होती है।\t5000\tobserved\tfinance\tकितना बचाऊँ?|कहाँ से शुरू करूँ?\n"
        "@x\tu2\tcarousel\tgym\tFive gym mistakes beginners make\t\t\tfitness\t\n")
    _, out, _ = a.r("post", "import", tsv)
    assert "added 2 post(s)" in out, out
    _, out, _ = a.r("post", "import", tsv)
    assert "added 0 post(s)" in out and "skipped 2" in out, out
    posts = a.load("posts.jsonl")
    assert posts[0]["language"] == "hi" and posts[0]["audience_questions"] == ["कितना बचाऊँ?", "कहाँ से शुरू करूँ?"]
    assert posts[1]["metrics"] == {}
    _, out, _ = a.r("search", "बचत", "--json")
    assert [p["id"] for p in json.loads(out)] == ["p-0001"], out
    _, out, _ = a.r("search", "mistakes", "--format", "carousel", "--json")
    assert [p["id"] for p in json.loads(out)] == ["p-0002"], out
    _, out, _ = a.r("search", "mistakes", "--format", "reel", "--json")
    assert json.loads(out) == []


@test("P6", "trends: a formula that appears now and not before is emerging, Hindi hooks included")
@with_archive
def _(a):
    for i, (hook, day) in enumerate([("Nobody tells you how rent works", "2026-11-10"),
                                     ("कोई आपको ये नहीं बताता कि बचत कैसे होती है।", "2026-11-12"),
                                     ("Steal this budget template", "2026-09-30")]):
        a.post(handle="@x", url=f"t{i}", hook=hook, observed_on=day, category="finance")
    _, out, _ = a.r("trends", "--days", "30", "--json")
    t = json.loads(out)
    nob = next(r for r in t["dimensions"]["formula"] if r["value"] == "Nobody Tells You")
    assert (nob["recent"], nob["prior"], nob["emerging"]) == (2, 0, True), nob
    assert (t["recent_posts"], t["prior_posts"]) == (2, 1), t


# ======================================================================
# research.py: ideas, recommendations, digest
# ======================================================================
@test("P7", "ideas: scores must be 1-5, insights must exist, near-duplicates are refused")
@with_archive
def _(a):
    rc, _, err = idea(a, "Budget in 60 seconds", rel=9)
    assert rc == 1 and "1 to 5" in err, err
    rc, _, err = idea(a, "Budget in 60 seconds", insights="p-0099")
    assert rc == 1 and "unknown post ids" in err, err
    assert idea(a, "Budget in 60 seconds")[0] == 0
    rc, _, err = idea(a, "Budget explained in 60 seconds")
    assert rc == 1 and "already have" in err, err
    assert idea(a, "Budget explained in 60 seconds", extra=["--allow-duplicate"])[0] == 0


@test("P8", "recommend: ranks by score, lifts approved, sinks repeats and ideas close to made content")
@with_archive
def _(a):
    a.post(handle="@x", url="u1", hook="Stop paying for unused subscriptions", adaptable="yes", adaptation="local angle")
    idea(a, "Gym membership traps", rel=5, orig=5, val=5, conf=4, eff=2)          # i-0001
    idea(a, "Subscriptions you forgot", insights="p-0001", rel=4, orig=4, val=4, conf=4, eff=2)   # i-0002
    idea(a, "Freelance invoice checklist", rel=3, orig=3, val=3, conf=3, eff=3)    # i-0003
    _, out, _ = a.r("recommend", "--json")
    assert [r["idea"]["id"] for r in json.loads(out)] == ["i-0001", "i-0002", "i-0003"], out
    a.r("idea", "status", "i-0003", "approved")
    a.r("recommend", "--mark")
    a.r("recommend", "--mark")
    _, out, _ = a.r("recommend", "--json")
    rec = {r["idea"]["id"]: r for r in json.loads(out)}
    assert rec["i-0001"]["cautions"] == ["recommended 2x before"], rec["i-0001"]
    a.r("idea", "status", "i-0002", "scripted")
    posts = a.load("posts.jsonl")
    assert posts[0]["used_in"] == ["i-0002"], posts[0]                    # the insight is now used
    _, out, _ = a.r("recommend", "--json")
    assert "i-0002" not in [r["idea"]["id"] for r in json.loads(out)]     # made ideas are not recommended
    rc, _, err = a.r("idea", "status", "i-0001", "posted", ok=False)
    assert rc == 1 and "status must be" in err


@test("P9", "digest: due accounts, new posts, outliers, unused insights, recommendations; --save writes it")
@with_archive
def _(a):
    a.r("account", "add", "--handle", "@x", "--priority", "high", "--baseline-views", "10000", "--baseline-basis", "observed")
    a.r("account", "add", "--handle", "@y")
    a.r("account", "done", "@y")
    a.post(handle="@x", url="u1", hook="Nobody tells you this about rent", views="40000", views_basis="observed",
           adaptable="yes", adaptation="a local version of the rent question")
    a.post(handle="@x", url="u2", hook="An estimated hit", views="99000", views_basis="estimate")
    idea(a, "Rent question, local version", insights="p-0001")
    _, out, _ = a.r("digest", "--save")
    assert "- @x (high) - never researched" in out and "@y" not in out.split("## New posts")[0], out
    assert "4.0x @x p-0001" in out and "p-0002" not in out.split("## Outliers")[1].split("## Trends")[0], out
    assert "99,000 (est.)" in out and "1 estimated values" in out, out
    assert "p-0001 @x: a local version of the rent question" in out, out
    assert "**i-0001 Rent question, local version**" in out and "from p-0001 @x" in out, out
    assert os.path.exists(os.path.join(a.dir, "digests", DAY + ".md"))
    assert a.load("ideas.jsonl")[0]["recommended"] == 1


# ======================================================================
# ig-reel/package.py
# ======================================================================
def spec_file(d, **over):
    spec = {"title": "Gym fees, read first", "why": "outlier", "audience": "first-time gym members", "target_seconds": 20,
            "hook": {"spoken": "बिना label पढ़े protein shake मत लीजिए।", "on_screen": "Label पढ़िए", "shot": "close up"},
            "scenes": [{"voiceover": "ज़्यादातर लोग सिर्फ़ flavour देखते हैं।", "shot": "talking head", "on_screen": "Flavour?"},
                       {"voiceover": "Protein per scoop और sugar देखिए।", "broll": "label close-up", "transition": "cut"}],
            "caption": "Protein shake लेने से पहले label पढ़िए।\n\nComment में LABEL लिखिए।",
            "topics": ["fitness"], "hashtags": ["#gym"],
            "claims": [{"claim": "labels list protein per serving", "source": "the product label", "status": "verified"}]}
    spec.update(over)
    p = os.path.join(d, "spec.json")
    json.dump(spec, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


@test("P10", "package: READY only with verified claims, shots for every scene and a caption")
def _():
    d = tempfile.mkdtemp()
    try:
        bank = os.path.join(d, "bank.json")
        json.dump({"always": ["#fitness"], "topics": {"fitness": ["#gymtips", "#protein", "#workout", "#health", "#diet"]}},
                  open(bank, "w"))
        rc, out, _ = run("ig-reel/package.py", spec_file(d), "--bank", bank, "--json")
        p = json.loads(out)
        assert rc == 0 and p["ready"] and p["problems"] == [], p["problems"]
        assert p["language"] == "mixed" and p["wpm"] == 150, (p["language"], p["wpm"])
        assert p["hashtags"] == ["#fitness", "#gym", "#gymtips", "#protein", "#workout"], p["hashtags"]  # capped at 5
        assert p["hook"]["uncalibrated"] is True
        rc, out, _ = run("ig-reel/package.py", spec_file(d, claims=[{"claim": "x", "status": "needs-check"}]))
        assert rc == 1 and "NOT READY" in out and "1 claim(s) not verified" in out, out
        assert "- [ ] Creator has shot the footage" in out and "this tool never publishes" in out
        rc, out, _ = run("ig-reel/package.py", spec_file(d, scenes=[{"voiceover": "बस इतना।"}]), "--json")
        assert rc == 1 and "scene 1 has no shot or B-roll: say what to film" in json.loads(out)["problems"], out
        rc, _, err = run("ig-reel/package.py", spec_file(d, scenes=[]))
        assert rc == 2 and "scenes" in err, err
    finally:
        shutil.rmtree(d)


# ======================================================================
# ig-carousel/render.py
# ======================================================================
def deck(d, slides, theme=None):
    p = os.path.join(d, "deck.json")
    json.dump({"slides": slides, **({"theme": theme} if theme else {})}, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


GOOD = [{"layout": "cover", "title": "Where does your salary go?", "visual": {"prompt": "3D jar of coins"}},
        {"layout": "statement", "text": "पैसा कम नहीं है। हिसाब नहीं है।"},
        {"layout": "stat", "value": "30", "label": "days of tracking", "source": "example"},
        {"layout": "cta", "title": "Want it?", "action": "Comment below", "keyword": "TRACK"}]


@test("P11", "carousel: renders every layout to HTML; stats need a source; visuals are honest placeholders")
def _():
    d = tempfile.mkdtemp()
    try:
        out = os.path.join(d, "out")
        rc, so, se = run("ig-carousel/render.py", deck(d, GOOD), "--out", out)
        assert rc == 0, se
        h = open(os.path.join(out, "carousel.html"), encoding="utf-8").read()
        for lay in ("l-cover", "l-statement", "l-stat", "l-cta"):
            assert f'class="slide {lay}"' in h, lay
        assert "VISUAL TO CREATE" in h and "3D jar of coins" in h and 'lang="hi"' in h and "01 / 04" in h
        rc, _, _ = run("ig-carousel/render.py", deck(d, [GOOD[0], dict(GOOD[1], source="Example Act, Section 2"), GOOD[3]]), "--out", out)
        h = open(os.path.join(out, "carousel.html"), encoding="utf-8").read()
        assert 'class="source slide-source"' in h and "Example Act, Section 2" in h
        bad = [dict(GOOD[0]), {"layout": "stat", "value": "72%", "label": "of buyers"}, {"layout": "zoom"}, GOOD[3]]
        rc, _, se = run("ig-carousel/render.py", deck(d, bad), "--check")
        assert rc == 1 and "No source, no stat" in se and "unknown layout" in se, se
        rc, _, se = run("ig-carousel/render.py", deck(d, [GOOD[0]]), "--check")
        assert rc == 1 and "Instagram takes 2 to 20" in se, se
    finally:
        shutil.rmtree(d)


@test("P12", "carousel: limits and order are warned; Hindi needs a Devanagari font; --strict fails warnings")
def _():
    d = tempfile.mkdtemp()
    try:
        long = [{"layout": "statement", "text": "x " * 90}, GOOD[0], GOOD[3]]
        rc, _, se = run("ig-carousel/render.py", deck(d, long), "--check")
        assert rc == 0 and "slide 1 is not a cover" in se and "the statement layout holds" in se, se
        rc, _, _ = run("ig-carousel/render.py", deck(d, long), "--check", "--strict")
        assert rc == 1
        theme = json.load(open(os.path.join(SK, "ig-carousel/themes/editorial.json")))
        theme["fonts"] = {"display_stack": ["Inter"], "body_stack": ["Inter"], "google": ["Inter"]}
        json.dump(theme, open(os.path.join(d, "latin.json"), "w"))
        rc, _, se = run("ig-carousel/render.py", deck(d, GOOD, "latin.json"), "--check")
        assert rc == 1 and "no Devanagari font" in se, se
    finally:
        shutil.rmtree(d)


@test("P13", "carousel: PNGs at 1080x1350 when node + Playwright are present (skipped otherwise)")
def _():
    if not shutil.which("node") or subprocess.run(["node", "-e", "require('playwright')"], capture_output=True).returncode:
        print("            (skipped: node with playwright not available)")
        return
    d = tempfile.mkdtemp()
    try:
        out = os.path.join(d, "out")
        rc, so, se = run("ig-carousel/render.py", deck(d, GOOD), "--out", out, "--png")
        assert rc == 0 and "wrote 4 PNG(s)" in so, (so, se)
        png = open(os.path.join(out, "slide_01.png"), "rb").read(32)
        w, h = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
        assert (w, h) == (1080, 1350), (w, h)
    finally:
        shutil.rmtree(d)


# ======================================================================
# ig-plan/content_calendar.py
# ======================================================================
@test("P14", "calendar: fills approved ideas by format, leaves OPEN slots, gates approval on verified facts")
@with_archive
def _(a):
    idea(a, "Gym fees, read first")                                           # i-0001 reel
    idea(a, "Five budget leaks", fmt="carousel")                              # i-0002 carousel
    idea(a, "Not approved yet")                                               # i-0003 stays new
    idea(a, "Already scripted reel about invoices", rel=2, orig=2, val=2, conf=2, eff=5)   # i-0004, low score
    a.r("idea", "status", "i-0001", "approved")
    a.r("idea", "status", "i-0002", "approved")
    a.r("idea", "status", "i-0004", "scripted")
    rc, out, _ = a.c("build", "--start", "2026-11-16", "--cadence", "mon:reel,wed:carousel,fri:reel")
    assert rc == 0, out
    cal = json.load(open(os.path.join(a.dir, "calendar.json")))
    assert [(s["date"], s["idea_id"]) for s in cal["slots"]] == [          # in production first, then approved
        ("2026-11-16", "i-0004"), ("2026-11-18", "i-0002"), ("2026-11-20", "i-0001")], cal
    a.c("build", "--start", "2026-11-23", "--cadence", "mon:reel")
    cal = json.load(open(os.path.join(a.dir, "calendar.json")))
    assert cal["slots"][-1] == dict(cal["slots"][-1], date="2026-11-23", idea_id="")   # nothing left: OPEN
    rc, out, _ = a.c("show")
    assert "OPEN: needs an idea" in out
    d = tempfile.mkdtemp()
    try:
        rc, out, _ = run("ig-reel/package.py", spec_file(d, claims=[{"claim": "x", "status": "needs-check"}]),
                         "--json", "-o", os.path.join(d, "pkg.json"))
        rc, out, _ = a.c("attach", "2026-11-16", "--package", os.path.join(d, "pkg.json"))
        assert "NOT verified" in out, out
        rc, _, err = a.c("approve", "2026-11-16", "--by", "creator")
        assert rc == 1 and "facts not done" in err, err
        run("ig-reel/package.py", spec_file(d), "--json", "-o", os.path.join(d, "pkg.json"))
        a.c("attach", "2026-11-16", "--package", os.path.join(d, "pkg.json"))
        rc, out, _ = a.c("approve", "2026-11-16", "--by", "creator")
        assert rc == 0 and "Publishing is still yours" in out, out
        rc, out, _ = a.c("check", "--days", "7")
        assert rc == 1 and "2026-11-16" not in out and "2 slot(s)" in out, out   # 23 Nov is past the window
        a.c("attach", "2026-11-16", "--package", os.path.join(d, "pkg.json"))     # a new package clears approval
        cal = json.load(open(os.path.join(a.dir, "calendar.json")))
        assert cal["slots"][0]["approval"] is None
    finally:
        shutil.rmtree(d)


@test("P15", "no new script writes bytecode into the skills folder")
def _():
    env = {k: v for k, v in ENV.items() if k != "PYTHONDONTWRITEBYTECODE"}
    a = Archive()
    try:
        subprocess.run([sys.executable, os.path.join(SK, "ig-viral/research.py"), "--data", a.dir, "status"],
                       env=env, capture_output=True)
        subprocess.run([sys.executable, os.path.join(SK, "ig-plan/content_calendar.py"), "--data", a.dir, "show"],
                       env=env, capture_output=True)
    finally:
        a.close()
    for d in ("ig-viral", "ig-plan", "ig-reel", "ig-caption", "ig-carousel"):
        assert not os.path.exists(os.path.join(SK, d, "__pycache__")), d


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

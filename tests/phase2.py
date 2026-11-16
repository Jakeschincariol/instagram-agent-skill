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



# ======================================================================
# fixes found while running the archive on real workflows (K1-K7)
# ======================================================================
def pkg(d, name, **body):
    p = os.path.join(d, name)
    json.dump(body, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


def one_slot(a):
    idea(a, "Gym fees, read first")
    a.r("idea", "status", "i-0001", "approved")
    a.c("build", "--start", "2026-11-16", "--cadence", "mon:reel")


@test("P16", "calendar (K1): package paths are stored relative to the data folder and survive a move")
def _():
    a = Archive()
    moved = tempfile.mkdtemp(prefix="ig_moved_")
    try:
        one_slot(a)
        os.makedirs(os.path.join(a.dir, "content"))
        ok = pkg(os.path.join(a.dir, "content"), "pkg.json", claims=[{"claim": "x", "source": "label", "status": "verified"}])
        rc, out, err = a.c("attach", "2026-11-16", "--package", ok)
        assert rc == 0, err
        stored = json.load(open(os.path.join(a.dir, "calendar.json")))["slots"][0]["package"]
        assert stored == "content/pkg.json", stored                       # no machine-specific path
        shutil.rmtree(moved); shutil.copytree(a.dir, moved)              # another checkout
        rc, out, err = run("ig-plan/content_calendar.py", "--data", moved, "--today", DAY, "approve", "2026-11-16", "--by", "c")
        assert rc == 0, err
        # an old calendar with an absolute path that is not on this machine: reported, not approved
        cal = json.load(open(os.path.join(a.dir, "calendar.json")))
        cal["slots"][0].update(package="/nowhere/old-checkout/pkg.json", approval=None)
        json.dump(cal, open(os.path.join(a.dir, "calendar.json"), "w"))
        rc, out, _ = a.c("check")
        assert rc == 1 and "package file not found here" in out, out
        rc, _, err = a.c("approve", "2026-11-16", "--by", "c")
        assert rc == 1 and "not on this machine" in err, err
    finally:
        a.close(); shutil.rmtree(moved, ignore_errors=True)


@test("P17", "calendar (K2): a missing or empty claims list never passes the facts gate")
@with_archive
def _(a):
    one_slot(a)
    d = tempfile.mkdtemp()
    try:
        for body in ({"title": "no claims key"}, {"title": "empty", "claims": []}):
            rc, out, _ = a.c("attach", "2026-11-16", "--package", pkg(d, "p.json", **body))
            assert rc == 0 and "NOT verified" in out and "no claims listed" in out, out
            rc, _, err = a.c("approve", "2026-11-16", "--by", "c")
            assert rc == 1 and "facts not done" in err, err
        # an explicit, recorded reason is the only way through without claims
        rc, out, _ = a.c("attach", "2026-11-16", "--package", pkg(d, "p.json", claims=[]),
                         "--no-claims", "a gym tour; states no rate, rule or number")
        assert rc == 0 and "facts verified (no claims: a gym tour" in out, out
        rc, out, err = a.c("approve", "2026-11-16", "--by", "c")
        assert rc == 0, err
        rc, _, err = a.c("attach", "2026-11-16", "--package", pkg(d, "q.json", claims=[{"claim": "x", "status": "needs-check"}]),
                         "--no-claims", "none")
        assert rc == 1 and "lists claims" in err, err
        rc, _, err = a.c("attach", "2026-11-16", "--package", pkg(d, "k.json", Claims=[{"claim": "x"}]),
                         "--no-claims", "none")                       # a misspelt key is not "no claims"
        assert rc == 1 and "lists claims under" in err, err
        for bad in ({"claims": "x"}, {"claims": {"a": 1}}, {"claims": ["x"]}):
            rc, _, err = a.c("attach", "2026-11-16", "--package", pkg(d, "bad.json", **bad))
            assert rc == 1 and "must be a list of objects" in err and "Traceback" not in err, (bad, err)
        json.dump([], open(os.path.join(d, "list.json"), "w"))
        rc, _, err = a.c("attach", "2026-11-16", "--package", os.path.join(d, "list.json"))
        assert rc == 1 and "expected a JSON object" in err, err
        rc, out, _ = a.c("attach", "2026-11-16", "--package", pkg(d, "v.json", claims=[{"claim": "x", "source": "s", "status": "verified"}]))
        open(os.path.join(d, "v.json"), "w").write("{bad")                  # corrupted after attach
        rc, _, err = a.c("approve", "2026-11-16", "--by", "c")
        assert rc == 1 and "not valid JSON" in err, err
        # a slot attached by the old code (facts_ok true, empty package): approve re-reads the package
        p = pkg(d, "old.json", title="old")
        cal = json.load(open(os.path.join(a.dir, "calendar.json")))
        cal["slots"][0].update(package=p, facts_ok=True, approval=None)
        cal["slots"][0].pop("no_claims", None)
        json.dump(cal, open(os.path.join(a.dir, "calendar.json"), "w"))
        rc, _, err = a.c("approve", "2026-11-16", "--by", "c")
        assert rc == 1 and "no claims listed" in err, err
        assert json.load(open(os.path.join(a.dir, "calendar.json")))["slots"][0]["facts_ok"] is False
    finally:
        shutil.rmtree(d)


@test("P18", "posts (K4): caption, post date, slide count and duration are kept")
@with_archive
def _(a):
    rc, _, err = a.post(handle="@x", url="https://www.instagram.com/p/C1/", format="carousel", hook="5 labels",
                        caption="Shake लेने से पहले label पढ़िए।\nSave कीजिए।", posted_on="2026-11-10", slides="8")
    assert rc == 0, err
    rc, _, err = a.post(handle="@x", url="https://www.instagram.com/reel/R1/", hook="Stop", duration_s="42s")
    assert rc == 0, err
    c, r = a.load("posts.jsonl")
    assert c["caption"].startswith("Shake लेने") and c["posted_on"] == "2026-11-10" and c["slides"] == 8, c
    assert r["duration_s"] == 42 and "slides" not in r and "posted_on" not in r, r
    rc, out, _ = a.r("search", "Save")
    assert "p-0001" in out, out                                       # caption is searchable
    for bad in ({"posted_on": "10/11/2026"}, {"slides": "0"}, {"slides": "eight"}, {"duration_s": "0:42"}):
        rc, _, err = a.post(handle="@x", url="https://www.instagram.com/p/BAD/", hook="h", **bad)
        assert rc == 1, (bad, err)
    assert len(a.load("posts.jsonl")) == 2


@test("P19", "posts (K5): one post under different URLs is stored once")
@with_archive
def _(a):
    rc, out, _ = a.post(handle="@x", url="https://www.instagram.com/reel/AbC_1-x/?igsh=MTd2", hook="h")
    assert rc == 0 and json.loads(open(os.path.join(a.dir, "posts.jsonl")).readline())["url"] == \
        "https://www.instagram.com/reel/AbC_1-x/", out
    for u in ("https://instagram.com/reel/AbC_1-x", "https://www.instagram.com/reels/AbC_1-x/",
              "https://m.instagram.com/reel/AbC_1-x/?utm_source=ig_web_copy_link", "https://www.instagram.com/p/AbC_1-x/",
              "https://www.instagram.com/someuser/reel/AbC_1-x/", " https://www.instagram.com/reel/AbC_1-x/ "):
        rc, out, _ = a.post(handle="@x", url=u, hook="h")
        assert rc == 0 and "skipped 1 already archived" in out, (u, out)
    rc, out, _ = a.post(handle="@x", url="https://www.instagram.com/reel/AbC_1-y/", hook="h")   # a different post
    assert "added 1" in out, out
    tsv = os.path.join(a.dir, "dup.tsv")                             # duplicates inside one import file
    open(tsv, "w").write("handle\turl\tformat\thook\n@x\thttps://www.instagram.com/p/Z9/\tcarousel\th\n"
                         "@x\thttps://www.instagram.com/p/Z9/?img_index=2\tcarousel\th\n")
    rc, out, _ = a.r("post", "import", tsv)
    assert "added 1" in out and "skipped 1" in out, out
    assert len(a.load("posts.jsonl")) == 3


@test("P20", "posts (K6): abbreviated counts are parsed, labelled and never cut to their digits")
@with_archive
def _(a):
    cases = [("12.4K", 12400, "12.4K"), ("1.2M", 1200000, "1.2M"), ("1.5 lakh", 150000, "1.5 lakh"),
             ("2 लाख", 200000, "2 लाख"), ("1,20,000", 120000, None), ("12,400", 12400, None), ("950", 950, None)]
    for i, (shown, value, label) in enumerate(cases):
        rc, _, err = a.post(handle="@x", url=f"https://www.instagram.com/reel/K{i}/", hook="h",
                            views=shown, views_basis="observed")
        assert rc == 0, (shown, err)
        m = a.load("posts.jsonl")[-1]["metrics"]["views"]
        assert m["value"] == value and m.get("shown") == label, (shown, m)
    for bad in ("12.4", "12.4X", "1.2.3K", "K"):
        rc, _, err = a.post(handle="@x", url="https://www.instagram.com/reel/BAD/", hook="h", views=bad, views_basis="observed")
        assert rc == 1 and ("not a number" in err or "unknown unit" in err or "no unit" in err), (bad, err)
    assert len(a.load("posts.jsonl")) == len(cases)
    a.r("account", "add", "--handle", "@y", "--baseline-views", "12.4K", "--baseline-basis", "observed")
    _, out, _ = a.r("account", "list", "--json")
    assert any(r["handle"] == "@y" and r["baseline_views"] == "12400" for r in json.loads(out)), out


@test("P21", "digest (K7): audience questions from the window, merged and counted")
@with_archive
def _(a):
    a.post(handle="@x", url="https://www.instagram.com/reel/Q1/", hook="h", observed_on="2026-11-14",
           audience_questions="Whey कब लेना चाहिए?|Sugar कितनी है?")
    a.post(handle="@x", url="https://www.instagram.com/reel/Q2/", hook="h", observed_on="2026-11-13",
           audience_questions="whey कब  लेना चाहिए|Price कितना है?")
    a.post(handle="@x", url="https://www.instagram.com/reel/Q3/", hook="h", observed_on="2026-10-01",
           audience_questions="Old question outside the window?")
    _, out, _ = a.r("digest", "--days", "7")
    sec = out.split("## Audience questions")[1].split("\n## ")[0]
    lines = [l for l in sec.splitlines() if l.startswith("- ")]
    assert lines[0].startswith('- "Whey कब लेना चाहिए?" (asked on 2 posts): p-0001, p-0002'), sec
    assert len(lines) == 3 and "Old question" not in sec, sec
    empty = Archive()
    try:
        _, out, _ = empty.r("digest")
        assert "## Audience questions" in out and "none captured in this window" in out, out
    finally:
        empty.close()

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

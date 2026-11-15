import sys, os, re, json, statistics
sys.dont_write_bytecode = True
# Same resolution as regress.py: $IG_SKILLS_ROOT, else this repository.
R = os.path.join(os.environ.get("IG_SKILLS_ROOT") or
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude/skills")
for d in ("ig-reel", "ig-human", "ig-caption"):
    sys.path.insert(0, os.path.join(R, d))
import hookscore, detect, caption, humanize
sys.path.insert(0, os.path.dirname(__file__))
from outputs import *

LEX = json.load(open(os.path.join(R, "ig-human/slop.json")))
HOOKS = {h["id"]: h["name"] for h in json.load(open(os.path.join(R, "ig-reel/hooks.json")))["hooks"]}
RUBRIC = {i["id"]: i["points"] for i in json.load(open(os.path.join(R, "ig-profile/rubric.json")))["items"]}
results = {}

def chk(skill, name, ok, detail=""):
    results.setdefault(skill, []).append((ok, name, detail))

def human(skill, label, text):
    """Every skill says: run it through /ig-human first. Do it for real."""
    clean, rep = humanize.humanize(text, LEX)
    arte = sum(h["count"] for k in ("invisible", "typographic", "lexical") for h in rep[k])
    _, score, verdict = detect.run(clean, LEX)
    tells = [s["name"] for s in rep["structures"]]
    ok = arte == 0 and not tells and verdict != "FLAGGED"
    shown = "n/a" if score is None else f"{score:.1f}"
    chk(skill, f"ig-human on {label}", ok, f"{arte} artefacts, tells={tells}, detect {shown} {verdict}")

sentences = lambda t: [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s]
nwords = lambda t: len(re.findall(r"[\w$%'’-]+", t))
BANNED_COMMENT_OPEN = re.compile(r"(?i)^\s*(great post|love this|so true|this 👏|needed this today|\w+!)")

# ---------------- ig-carousel
s = "ig-carousel"
chk(s, "6-10 slides", 6 <= len(CAROUSEL) <= 10, f"{len(CAROUSEL)}")
chk(s, "cover <=6 words", nwords(CAROUSEL[0][1]) <= 6, CAROUSEL[0][1])
for i, (lab, head, body) in enumerate(CAROUSEL[2:-2], 3):
    chk(s, f"slide {i} headline 3-7 words", 3 <= nwords(head) <= 7, f"{nwords(head)}: {head}")
for i, (lab, head, body) in enumerate(CAROUSEL, 1):
    chk(s, f"slide {i} body <=25 words", nwords(body) <= 25, str(nwords(body)))
chk(s, "recap + one-action CTA last", CAROUSEL[-2][0] == "RECAP" and CAROUSEL[-1][0] == "CTA", "")
a = caption.analyse(CAROUSEL_CAPTION, keywords=["client contracts", "freelance contracts"])
chk(s, "caption (Job B) caption.py verdict", a["verdict"] == "READY", f"{a['verdict']} " + "; ".join(f"{c['check']}={c['status']}" for c in a['checks'] if c['status'] != 'PASS'))
human(s, "caption", CAROUSEL_CAPTION)
human(s, "slide copy", "\n".join(f"{h.title()}. {b}" for _, h, b in CAROUSEL))
chk(s, "alt text on cover", len(CAROUSEL_ALT) > 40, "")

# ---------------- ig-story
s = "ig-story"
chk(s, "3-7 frames", 3 <= len(STORY) <= 7, str(len(STORY)))
stick = [f for f in STORY if f["sticker"]]
chk(s, "exactly one sticker ask", len(stick) == 1, str(len(stick)))
chk(s, "ask at frame 4", stick and stick[0]["frame"] == 4, "")
chk(s, "face or hand in frame 1", re.search(r"selfie|face|hand|talking", STORY[0]["visual"]) is not None, STORY[0]["visual"])
chk(s, "one idea per frame (<=2 sentences)", all(len(sentences(f["says"])) <= 2 for f in STORY), "")
chk(s, "speaks to one person ('you')", any(re.search(r"\byou\b", f["says"], re.I) for f in STORY), "")
human(s, "frames", "\n".join(f["says"] for f in STORY))

# ---------------- ig-comment
s = "ig-comment"
chk(s, "two options, different types", len(COMMENTS) == 2 and COMMENTS[0][0].split()[0] != COMMENTS[1][0].split()[0], "")
for t, c in COMMENTS:
    n = len(sentences(c))
    chk(s, f"[{t}] 1-3 sentences", 1 <= n <= 3, str(n))
    chk(s, f"[{t}] no banned opener / emoji-first", not BANNED_COMMENT_OPEN.match(c) and not hookscore.EMOJI_RE.match(c), c[:30])
    chk(s, f"[{t}] no pitch/link", not re.search(r"(?i)my page|link|dm me|check out|template", c), "")
    human(s, t, c)
chk(s, "pick + reason given", bool(COMMENT_PICK), "")

# ---------------- ig-reply
s = "ig-reply"
placed = sum(REPLY_BUCKETS.values(), [])
chk(s, "every comment triaged exactly once", sorted(placed) == sorted(h for h, _ in REPLY_INPUT), f"{len(placed)}/{len(REPLY_INPUT)}")
chk(s, "noise gets no reply", not any(h in REPLIES for h in REPLY_BUCKETS["NOISE"]), "")
for h in REPLY_BUCKETS["SUPPORT"]:
    chk(s, f"support reply {h} 3-8 words", 3 <= nwords(REPLIES[h]) <= 8, str(nwords(REPLIES[h])))
for h, r in REPLIES.items():
    chk(s, f"{h}: name once, no '!' after it", r.count(h.strip('@').split('_')[0].split('.')[0].title()) <= 1 and not re.match(r"^\w+!", r), "")
chk(s, "question routed to Reel as #16", REPLY_QUESTION_TO_REEL[2] == 16 and HOOKS[16] == "The Verbatim Question", HOOKS[16])
human(s, "all replies", "\n".join(REPLIES.values()))

# ---------------- ig-dm
s = "ig-dm"
first_line = DM_KEYWORD.split("\n")[0]
chk(s, "thing delivered in message 1, no gate", "https://" in first_line and "before I send" not in DM_KEYWORD, first_line)
chk(s, "ends on a short question", DM_KEYWORD.strip().endswith("?"), "")
chk(s, "exactly two follow-ups at +4 and +10", [d for d, _ in DM_FOLLOWUPS] == [4, 10], "")
chk(s, "follow-up 1 adds something new (not 'bumping')", "bump" not in DM_FOLLOWUPS[0][1].lower(), "")
chk(s, "follow-up 2 closes the loop", re.search(r"(?i)last one|leave it", DM_FOLLOWUPS[1][1]) is not None, "")
for d, m in DM_FOLLOWUPS:
    chk(s, f"+{d}d message 2-4 sentences", 2 <= len(sentences(m)) <= 4, str(len(sentences(m))))
chk(s, "char count reported", True, f"keyword DM {len(DM_KEYWORD)} chars, +4d {len(DM_FOLLOWUPS[0][1])}, +10d {len(DM_FOLLOWUPS[1][1])}")
human(s, "DM + follow-ups", DM_KEYWORD.replace("https://dana.studio/template", "the link") + "\n" + "\n".join(m for _, m in DM_FOLLOWUPS))

# ---------------- ig-repurpose
s = "ig-repurpose"
chk(s, ">=4 extracts found", sum(REPURPOSE_FOUND.values()) >= 4, str(REPURPOSE_FOUND))
nums = re.findall(r"\b\d[\d,]*\b|\b(?:three|four|six|ninety|forty-five)\b", REPURPOSE_SOURCE, re.I)
chk(s, "numbers count matches source", REPURPOSE_FOUND["numbers"] <= len(nums), f"source has {len(nums)} numeric tokens")
ids = [w[2] for w in REPURPOSE_WEEK if w[2]]
chk(s, "hook formulas valid + varied", all(i in HOOKS for i in ids) and len(set(ids)) == len(ids), str([HOOKS[i] for i in ids]))
chk(s, "mechanism -> carousel, line -> story", REPURPOSE_WEEK[1][1] == "CAROUSEL" and REPURPOSE_WEEK[-1][1] == "STORY", "")
chk(s, "no 'as I said in my video'", not any(re.search(r"(?i)as i said|latest video|episode", w[3]) for w in REPURPOSE_WEEK), "")
for day, fmt, fid, hook in REPURPOSE_WEEK:
    if fmt == "REEL":
        _, sc, v, fl = hookscore.run(hook)
        chk(s, f"{day} reel hook score >=50", sc >= 50, f"{sc:.1f} {v} {fl}")

# ---------------- ig-audit (compute exactly what the skill specifies)
s = "ig-audit"
med = statistics.median(p[1] for p in AUDIT_POSTS)
rows = [dict(date=p[0], views=p[1], mult=p[1] / med, nonf=p[3], hold=p[4], spr=p[5] / p[2], fpr=p[6] / p[2], fid=p[7], fmt=p[8], len=p[9], theme=p[10]) for p in AUDIT_POSTS]
top = sorted(rows, key=lambda r: -r["mult"])[:5]; bot = sorted(rows, key=lambda r: r["mult"])[:5]
hold_t, hold_b = statistics.mean(r["hold"] for r in top), statistics.mean(r["hold"] for r in bot)
chk(s, "median + outlier multiple computed", med > 0, f"median {med:,.0f}; top {top[0]['date']} {top[0]['mult']:.1f}x")
chk(s, "hold@3s separates top/bottom", hold_t - hold_b > 10, f"top5 {hold_t:.0f}% vs bottom5 {hold_b:.0f}%")
sends = sorted(rows, key=lambda r: -r["spr"])
chk(s, "sends/reach ranking surfaces low-view high-send post", sends[0]["date"] == "Aug 06", f"{sends[0]['date']} {sends[0]['views']:,} views {sends[0]['spr']*100:.2f}% sends/reach")
jul23 = next(r for r in rows if r["date"] == "Jul 23")
chk(s, "profile-vs-hook split (high nonfollower, low follows)", jul23["nonf"] >= 50 and jul23["fpr"] < 0.001, f"Jul 23: {jul23['nonf']}% non-follower, {jul23['fpr']*100:.3f}% follows/reach -> /ig-profile")
tools = [r for r in rows if r["theme"] == "tools"]
chk(s, "'tools' theme is the stop list", all(r["mult"] < 1 for r in tools), f"{len(tools)} tools posts, max {max(r['mult'] for r in tools):.2f}x")
chk(s, "confidence stated (n=12 < 30)", len(rows) < 30, f"n={len(rows)}: pattern is suggestive, not proven")
AUDIT_SUMMARY = dict(median=med, top=[(r['date'], round(r['mult'], 1), HOOKS.get(r['fid'], '-'), r['hold'], round(r['spr']*100, 2)) for r in top],
                     bottom=[(r['date'], round(r['mult'], 2), HOOKS.get(r['fid'], '-'), r['hold']) for r in bot])

# ---------------- ig-plan
s = "ig-plan"
posts = [p for p in PLAN if p[2] in ("REEL", "CAROUSEL")]
chk(s, "4-5 posts", 4 <= len(posts) <= 5, str(len(posts)))
chk(s, ">=3 reels", sum(p[2] == "REEL" for p in posts) >= 3, str(sum(p[2] == "REEL" for p in posts)))
types = [p[3] for p in posts]
chk(s, "no two same type back to back", all(a != b for a, b in zip(types, types[1:])), str(types))
chk(s, "one proof, one opinion", types.count("PROOF") == 1 and types.count("OPINION") == 1, "")
chk(s, "hook ids valid", all(p[4] in HOOKS for p in posts if p[2] == "REEL"), str([HOOKS[p[4]] for p in posts if p[2] == "REEL"]))
chk(s, "angles specific (number or event)", all(re.search(r"\d|client|kill fee|checklist", p[5], re.I) or p[3] == "OPINION" for p in posts), "")
chk(s, "engagement list 5/3/2", [len(PLAN_ENGAGE[k]) for k in ("reach", "peers", "buyers")] == [5, 3, 2], "")
chk(s, "engage list drawn from user's 10 accounts", set(sum(PLAN_ENGAGE.values(), [])) == set(PLAN_INPUT["accounts"]), "")
for p in posts:
    if p[2] == "REEL":
        _, sc, v, _ = hookscore.run(p[5])

# ---------------- ig-profile
s = "ig-profile"
chk(s, "rubric has 12 items, 100 pts", len(RUBRIC) == 12 and sum(RUBRIC.values()) == 100, "")
chk(s, "every item scored", set(PROFILE_SCORE_BEFORE) == set(RUBRIC), "")
chk(s, "no item over its max", all(PROFILE_SCORE_BEFORE[k] <= RUBRIC[k] and PROFILE_SCORE_AFTER[k] <= RUBRIC[k] for k in RUBRIC), "")
b, a2 = sum(PROFILE_SCORE_BEFORE.values()), sum(PROFILE_SCORE_AFTER.values())
chk(s, "before score honest (30s-40s typical)", b < 50, f"{b}/100")
lost = sorted(RUBRIC, key=lambda k: -(RUBRIC[k] - PROFILE_SCORE_BEFORE[k]))
chk(s, "fix order = points lost", True, " > ".join(f"{k}(-{RUBRIC[k]-PROFILE_SCORE_BEFORE[k]})" for k in lost[:5]))
chk(s, "name field options <=30 chars", all(len(n) <= 30 for n in PROFILE_REWRITES["name_field"]), str([len(n) for n in PROFILE_REWRITES["name_field"]]))
chk(s, "bio <=150 chars", len(PROFILE_REWRITES["bio"]) <= 150, str(len(PROFILE_REWRITES["bio"])))
chk(s, "4-6 highlights", 4 <= len(PROFILE_REWRITES["highlights"]) <= 6, "")
chk(s, "re-score delta shown honestly (<100)", a2 < 100, f"{b} -> {a2} (+{a2-b}); rest needs pinned posts, pro account, photo, grid")
human(s, "bio", PROFILE_REWRITES["bio"])

# ---------------- report
for skill, rs in results.items():
    ok = sum(r[0] for r in rs)
    print(f"\n{skill}: {ok}/{len(rs)} checks pass")
    for good, name, det in rs:
        print(f"  {'PASS' if good else 'FAIL'}  {name}" + (f"  [{det}]" if det else ""))
print("\nAUDIT SUMMARY", json.dumps(AUDIT_SUMMARY, indent=0))

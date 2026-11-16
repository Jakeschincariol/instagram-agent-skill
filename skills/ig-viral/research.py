#!/usr/bin/env python3
"""
research.py - the research archive behind /ig-viral: which accounts to watch,
what their posts did, what is trending across them, and which content ideas to
make next.

It stores what you, or an authorised browser session, actually saw. It never
fetches Instagram itself and never fills in a number nobody observed: every
metric carries a basis, "observed" (read off the post) or "estimate" (your
guess, kept apart), and a metric without one is refused.

Data lives in one folder, outside this repository unless you point it at one:
  --data DIR, or $IG_RESEARCH_DIR, or ~/.claude/instagram/research
    accounts.tsv   the registry: accounts you watch and accounts discovered
    posts.jsonl    one observed Reel or carousel per line
    ideas.jsonl    content ideas, linked to the posts that inspired them
    digests/       saved research digests

Usage
  research.py init
  research.py account add --handle @x --name "X" --niche "real estate" --why "..." --priority high
  research.py account import accounts.tsv
  research.py account list [--due 14] [--status active]
  research.py account done @x                  # researched today
  research.py discover add --handle @y --why "..." --found-via "web search: ..."
  research.py discover list | promote @y | reject @y
  research.py post add --json '{"handle": "@x", "url": "...", "format": "reel", ...}'
  research.py post import posts.tsv            # or .jsonl
  research.py search "plot" [--format reel] [--handle @x]
  research.py outliers [--min 2]
  research.py trends [--days 30]
  research.py idea add --title "..." --format reel --insights p-0001 --relevance 5 ...
  research.py idea status i-0001 scripted
  research.py recommend [-n 5] [--mark]
  research.py digest [--days 7] [--save]

Exit status: 0 ok, 1 a check failed (nothing written), 2 bad usage.
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import statistics
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:                                     # hook formulas and Hindi-aware language detection
    from swipe import HOOKS, classify, lang_of, load_formulas  # noqa: E402
except Exception:                        # copied on its own: formulas unnamed
    HOOKS, classify, load_formulas = None, None, None

    def lang_of(text):
        return "hi" if re.search("[" + chr(0x0900) + "-" + chr(0x097F) + "]", text) else "en"

ACCOUNT_COLS = ["handle", "name", "niche", "why", "priority", "source", "status", "added",
                "last_researched", "baseline_views", "baseline_basis", "found_via", "notes"]
PRIORITIES = {"high": 3, "medium": 2, "low": 1, "3": 3, "2": 2, "1": 1}
ACCOUNT_STATUS = {"active", "candidate", "paused", "rejected"}
FORMATS = {"reel", "carousel", "post", "story"}
METRICS = ["views", "likes", "comments", "shares", "saves"]
BASES = {"observed", "estimate"}
IDEA_STATUS = ["new", "approved", "scripted", "shot", "edited", "ready", "published", "parked", "rejected"]
CONVERTED = {"scripted", "shot", "edited", "ready", "published"}
OPEN = {"new", "approved"}
SCORE_FIELDS = ["relevance", "originality", "value", "confidence", "effort"]
WEIGHTS = {"relevance": 0.30, "originality": 0.20, "value": 0.25, "confidence": 0.15, "effort": 0.10}


class Refused(Exception):
    """A check failed. Nothing is written."""


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------
def data_dir(arg=None):
    return os.path.expanduser(arg or os.environ.get("IG_RESEARCH_DIR") or "~/.claude/instagram/research")


def today(arg=None):
    return arg or dt.date.today().isoformat()


def norm_handle(h):
    h = (h or "").strip()
    h = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", h, flags=re.I).split("?")[0].strip("/")
    if not h:
        raise Refused("a handle is required")
    h = h.lstrip("@").lower()
    if not re.fullmatch(r"[a-z0-9._]{1,30}", h):         # Instagram's own rule for usernames
        raise Refused(f"{h!r} is not an Instagram handle (letters, digits, . and _, up to 30). "
                      "If the handle is not known yet, keep the name in a to-find list instead")
    return "@" + h


POST_URL = re.compile(r"^https?://(?:www\.|m\.)?instagram\.com/(?:[A-Za-z0-9._]+/)?(reels?|p|tv)/([A-Za-z0-9_-]+)", re.I)


def canonical_url(url):
    """One URL per post: ?igsh= and other query strings, /reels/ vs /reel/, m. or no www,
    and a username prefix all point at the same post. Non-Instagram URLs are only trimmed."""
    url = (url or "").strip()
    m = POST_URL.match(url)
    if not m:
        return url
    kind = "reel" if m.group(1).lower().startswith("reel") else ("tv" if m.group(1).lower() == "tv" else "p")
    return f"https://www.instagram.com/{kind}/{m.group(2)}/"


def post_key(url):
    """What makes two URLs the same post: the shortcode, whatever the path kind."""
    m = POST_URL.match((url or "").strip())
    return ("ig", m.group(2)) if m else ("url", canonical_url(url))


SCALE = {"k": 10**3, "thousand": 10**3, "हज़ार": 10**3, "हजार": 10**3,
         "m": 10**6, "mn": 10**6, "million": 10**6,
         "l": 10**5, "lac": 10**5, "lakh": 10**5, "lakhs": 10**5, "लाख": 10**5,
         "cr": 10**7, "crore": 10**7, "crores": 10**7, "करोड़": 10**7, "b": 10**9, "billion": 10**9}
NUMBER = re.compile(r"^(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d+))?\s*([^\d\s.,]*)$")


def parse_count(text):
    """A count as Instagram shows it -> (int, shown). "12,400" -> (12400, None);
    "12.4K" -> (12400, "12.4K"); "1.2 लाख" -> (120000, "1.2 लाख"). `shown` keeps the
    rounded label so nobody mistakes 12400 for an exact count. Anything else is refused,
    never reduced to its digits ("12.4K" used to become 124)."""
    s = str(text).strip()
    m = NUMBER.match(s)
    if not m:
        raise Refused(f"{s!r} is not a number. Write it as the post shows it (12,400 or 12.4K)")
    whole, frac, unit = m.group(1).replace(",", ""), m.group(2), m.group(3).lower()
    if unit and unit not in SCALE:
        raise Refused(f"{s!r}: unknown unit {m.group(3)!r} (use K, M, lakh or crore)")
    if not unit:
        if frac:
            raise Refused(f"{s!r} has a decimal but no unit: is it 12.4K?")
        return int(whole), None
    from decimal import Decimal
    return int(Decimal(whole + "." + (frac or "0")) * SCALE[unit]), s


class Store:
    def __init__(self, root):
        self.root = root
        self.accounts_path = os.path.join(root, "accounts.tsv")
        self.posts_path = os.path.join(root, "posts.jsonl")
        self.ideas_path = os.path.join(root, "ideas.jsonl")
        self.digests = os.path.join(root, "digests")

    def init(self):
        os.makedirs(self.digests, exist_ok=True)
        if not os.path.exists(self.accounts_path):
            self.save_accounts([])
        for p in (self.posts_path, self.ideas_path):
            if not os.path.exists(p):
                open(p, "w", encoding="utf-8").close()

    def need(self):
        if not os.path.exists(self.accounts_path):
            raise Refused(f"no research archive at {self.root}. Run: research.py init")

    # accounts ---------------------------------------------------------------
    def accounts(self):
        self.need()
        with open(self.accounts_path, encoding="utf-8", newline="") as fh:
            return [{c: (r.get(c) or "") for c in ACCOUNT_COLS} for r in csv.DictReader(fh, delimiter="\t")]

    def save_accounts(self, rows):
        with open(self.accounts_path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=ACCOUNT_COLS, delimiter="\t", lineterminator="\n")
            w.writeheader()
            for r in sorted(rows, key=lambda r: (-PRIORITIES.get(r["priority"], 0), r["handle"])):
                w.writerow({c: r.get(c, "") for c in ACCOUNT_COLS})

    # posts and ideas -------------------------------------------------------
    def _load(self, path):
        self.need()
        out = []
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        raise Refused(f"{os.path.basename(path)} line {n} is not valid JSON: {e}")
        return out

    def _save(self, path, rows):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def posts(self):
        return self._load(self.posts_path)

    def ideas(self):
        return self._load(self.ideas_path)

    def save_posts(self, rows):
        self._save(self.posts_path, rows)

    def save_ideas(self, rows):
        self._save(self.ideas_path, rows)


def next_id(rows, prefix):
    nums = [int(r["id"].split("-")[1]) for r in rows if re.match(prefix + r"-\d+$", r.get("id", ""))]
    return f"{prefix}-{(max(nums) + 1) if nums else 1:04d}"


# ---------------------------------------------------------------------------
# accounts and discovery
# ---------------------------------------------------------------------------
def clean_account(fields, source="manual", status="active", on=None):
    a = {c: str(fields.get(c) or "").strip() for c in ACCOUNT_COLS}
    a["handle"] = norm_handle(a["handle"])
    pr = (a["priority"] or "medium").lower()
    if pr not in PRIORITIES:
        raise Refused(f"{a['handle']}: priority must be high, medium or low, not {a['priority']!r}")
    a["priority"] = {"3": "high", "2": "medium", "1": "low"}.get(pr, pr)
    a["source"] = a["source"] or source
    a["status"] = (a["status"] or status).lower()
    if a["status"] not in ACCOUNT_STATUS:
        raise Refused(f"{a['handle']}: status must be one of {sorted(ACCOUNT_STATUS)}")
    a["added"] = a["added"] or today(on)
    if a["baseline_views"]:
        try:
            digits = str(parse_count(a["baseline_views"])[0])
        except Refused as e:
            raise Refused(f"{a['handle']}: baseline_views: {e}")
        if a["baseline_basis"] not in BASES:
            raise Refused(f"{a['handle']}: baseline_views needs baseline_basis observed or estimate. "
                          "A number nobody can trace is not kept.")
        a["baseline_views"] = digits
    return a


def upsert_accounts(store, new_rows):
    rows = {r["handle"]: r for r in store.accounts()}
    added = updated = 0
    for a in new_rows:
        if a["handle"] in rows:
            old = rows[a["handle"]]
            for c in ACCOUNT_COLS:
                if a[c] and c not in ("added",):
                    old[c] = a[c]
            updated += 1
        else:
            rows[a["handle"]] = a
            added += 1
    store.save_accounts(list(rows.values()))
    return added, updated


def read_table(path):
    """TSV or CSV with a header row -> list of dicts (keys lower-cased)."""
    raw = open(path, encoding="utf-8").read()
    delim = "\t" if "\t" in raw.splitlines()[0] else ","
    rows = list(csv.DictReader(io.StringIO(raw), delimiter=delim))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in rows]


def due_accounts(accounts, days, on=None):
    ref = dt.date.fromisoformat(today(on))
    out = []
    for a in accounts:
        if a["status"] != "active":
            continue
        last = a["last_researched"]
        age = (ref - dt.date.fromisoformat(last)).days if last else None
        if age is None or age >= days:
            out.append((a, age))
    return sorted(out, key=lambda x: (-PRIORITIES.get(x[0]["priority"], 0), -(x[1] if x[1] is not None else 10 ** 6)))


# ---------------------------------------------------------------------------
# posts
# ---------------------------------------------------------------------------
POST_TEXT = ["topic", "category", "hook", "on_screen", "structure", "visual_style", "why_it_works",
             "adaptation", "notes", "language", "caption"]
POST_NUMBERS = {"slides": int, "duration_s": float}     # slide count for carousels, length for reels


def clean_post(raw, on=None):
    p = {k: (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
    out = {"handle": norm_handle(p.get("handle") or p.get("account")),
           "url": canonical_url(p.get("url") or p.get("post_url") or "")}
    fmt = (p.get("format") or "").lower()
    if fmt not in FORMATS:
        raise Refused(f"format must be one of {sorted(FORMATS)}, not {fmt!r}")
    out["format"] = fmt
    for k in POST_TEXT:
        if p.get(k):
            out[k] = str(p[k])
    if not out.get("hook") and not out.get("topic"):
        raise Refused("a post needs at least a hook or a topic")
    if out.get("hook") and not out.get("language"):
        out["language"] = lang_of(out["hook"])
    posted = str(p.get("posted_on") or p.get("posted") or "").strip()
    if posted:
        try:
            dt.date.fromisoformat(posted)
        except ValueError:
            raise Refused(f"posted_on must be a date like 2026-11-10, not {posted!r}")
        out["posted_on"] = posted
    for k, kind in POST_NUMBERS.items():
        v = str(p.get(k) if p.get(k) is not None else "").strip()
        if v:
            try:
                n = kind(v.rstrip("s"))
            except ValueError:
                raise Refused(f"{k} must be a number, not {v!r}")
            if n <= 0:
                raise Refused(f"{k} must be above 0, not {v!r}")
            out[k] = int(n) if kind is int or n == int(n) else n
    q = p.get("audience_questions") or []
    out["audience_questions"] = [x.strip() for x in (q.split("|") if isinstance(q, str) else q) if x.strip()]
    adapt = str(p.get("adaptable") or "").lower()
    if adapt and adapt not in ("yes", "no", "maybe"):
        raise Refused("adaptable must be yes, no or maybe")
    if adapt:
        out["adaptable"] = adapt
    metrics = {}
    given = p.get("metrics") or {}
    for m in METRICS:
        val = given.get(m, {}).get("value") if isinstance(given.get(m), dict) else p.get(m)
        basis = given.get(m, {}).get("basis") if isinstance(given.get(m), dict) else p.get(m + "_basis")
        if val in (None, ""):
            continue
        try:
            number, shown = parse_count(val)
        except Refused as e:
            raise Refused(f"{m}: {e}")
        basis = (basis or "").lower()
        if basis not in BASES:
            raise Refused(f"{m}={val} has no basis. Say {m}_basis observed (read off the post) or estimate. "
                          "A number nobody saw is not stored.")
        metrics[m] = {"value": number, "basis": basis}
        if shown:
            metrics[m]["shown"] = shown
    out["metrics"] = metrics
    out["observed_on"] = p.get("observed_on") or today(on)
    out["captured_by"] = p.get("captured_by") or "manual"
    out["used_in"] = p.get("used_in") or []
    return out


def add_posts(store, raws, on=None):
    posts = store.posts()
    seen = {post_key(p["url"]) for p in posts if p.get("url")}
    accounts = {a["handle"] for a in store.accounts()}
    cleaned, skipped, unknown = [], [], set()
    for r in raws:
        p = clean_post(r, on)
        if p["url"] and post_key(p["url"]) in seen:
            skipped.append(p["url"])
            continue
        if p["handle"] not in accounts:
            unknown.add(p["handle"])
        p["id"] = next_id(posts + cleaned, "p")
        if p["url"]:
            seen.add(post_key(p["url"]))
        cleaned.append(p)
    store.save_posts(posts + cleaned)
    return cleaned, skipped, sorted(unknown)


def baselines(accounts, posts):
    """Per account: (views baseline, how it was set). Observed numbers only."""
    out = {}
    for a in accounts:
        if a["baseline_views"] and a["baseline_basis"] == "observed":
            out[a["handle"]] = (int(a["baseline_views"]), "registry median (observed)")
    by = {}
    for p in posts:
        v = p["metrics"].get("views")
        if v and v["basis"] == "observed":
            by.setdefault(p["handle"], []).append(v["value"])
    for h, vals in by.items():
        if h not in out and len(vals) >= 3:
            out[h] = (int(statistics.median(vals)), f"median of {len(vals)} archived posts")
    return out


def outliers(accounts, posts, minimum=1.0):
    base = baselines(accounts, posts)
    rows = []
    for p in posts:
        v = p["metrics"].get("views")
        if not v or v["basis"] != "observed" or p["handle"] not in base:
            continue
        b, how = base[p["handle"]]
        if b:
            rows.append((round(v["value"] / b, 2), p, b, how))
    return [r for r in sorted(rows, key=lambda r: -r[0]) if r[0] >= minimum]


def post_text(p):
    return " ".join(str(p.get(k, "")) for k in ("handle", "topic", "category", "hook", "on_screen",
                                                  "structure", "visual_style", "why_it_works", "adaptation",
                                                  "notes", "caption")) + " " + " ".join(p.get("audience_questions", []))


def search(posts, query, fmt=None, handle=None, since=None):
    terms = [t.casefold() for t in query.split()]
    out = []
    for p in posts:
        if fmt and p["format"] != fmt:
            continue
        if handle and p["handle"] != norm_handle(handle):
            continue
        if since and p["observed_on"] < since:
            continue
        text = post_text(p).casefold()
        if all(t in text for t in terms):
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# trends
# ---------------------------------------------------------------------------
def formula_of(p, formulas):
    if not formulas or not p.get("hook"):
        return "unclassified"
    return classify(p["hook"], formulas)[1]


def trends(posts, days=30, on=None, formulas=None):
    """Compare the last `days` with the `days` before. A pattern is emerging
    when it appears at least twice now and its share has grown by half, or it
    is new."""
    ref = dt.date.fromisoformat(today(on))
    lo_recent = (ref - dt.timedelta(days=days)).isoformat()
    lo_prior = (ref - dt.timedelta(days=2 * days)).isoformat()
    recent = [p for p in posts if p["observed_on"] > lo_recent]
    prior = [p for p in posts if lo_prior < p["observed_on"] <= lo_recent]
    dims = {"formula": lambda p: formula_of(p, formulas), "format": lambda p: p["format"],
            "category": lambda p: p.get("category", "").lower() or None,
            "structure": lambda p: p.get("structure", "").lower() or None,
            "visual_style": lambda p: p.get("visual_style", "").lower() or None,
            "language": lambda p: p.get("language")}
    result = {}
    for dim, key in dims.items():
        rc, pc = {}, {}
        for p in recent:
            k = key(p)
            if k:
                rc[k] = rc.get(k, 0) + 1
        for p in prior:
            k = key(p)
            if k:
                pc[k] = pc.get(k, 0) + 1
        rows = []
        for k, n in rc.items():
            share = n / max(len(recent), 1)
            before = pc.get(k, 0) / max(len(prior), 1)
            emerging = n >= 2 and (pc.get(k, 0) == 0 or share >= before * 1.5)
            rows.append({"value": k, "recent": n, "prior": pc.get(k, 0), "emerging": emerging})
        result[dim] = sorted(rows, key=lambda r: (-r["emerging"], -r["recent"], r["value"]))
    return {"window_days": days, "recent_posts": len(recent), "prior_posts": len(prior), "dimensions": result}


# ---------------------------------------------------------------------------
# ideas and recommendations
# ---------------------------------------------------------------------------
def tokens(text):
    return {t for t in re.findall(r"\w+", (text or "").casefold()) if len(t) > 2}


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def add_idea(store, fields, on=None):
    ideas, posts = store.ideas(), store.posts()
    if not fields.get("title"):
        raise Refused("an idea needs a title")
    fmt = (fields.get("format") or "").lower()
    if fmt not in ("reel", "carousel", "both"):
        raise Refused("format must be reel, carousel or both")
    scores = {}
    for f in SCORE_FIELDS:
        v = fields.get(f)
        if v is None or not str(v).isdigit() or not 1 <= int(v) <= 5:
            raise Refused(f"{f} must be a whole number from 1 to 5 (effort: 1 = easy to produce, 5 = hard)")
        scores[f] = int(v)
    ids = {p["id"] for p in posts}
    insights = [x.strip() for x in (fields.get("insights") or []) if x.strip()]
    missing = [x for x in insights if x not in ids]
    if missing:
        raise Refused(f"unknown post ids: {', '.join(missing)}")
    text = fields["title"] + " " + (fields.get("angle") or "")
    dupes = [i["id"] for i in ideas if i["status"] != "rejected"
             and similarity(text, i["title"] + " " + i.get("angle", "")) >= 0.6]
    if dupes and not fields.get("allow_duplicate"):
        raise Refused(f"looks like an idea you already have ({', '.join(dupes)}). "
                      "Refine that one, or pass --allow-duplicate")
    idea = {"id": next_id(ideas, "i"), "title": fields["title"], "format": fmt,
            "angle": fields.get("angle") or "", "audience": fields.get("audience") or "",
            "pillar": fields.get("pillar") or "", "insights": insights, "scores": scores,
            "status": "new", "created": today(on), "recommended": 0, "last_recommended": "",
            "history": [{"on": today(on), "status": "new"}], "notes": fields.get("notes") or ""}
    store.save_ideas(ideas + [idea])
    return idea


def set_status(store, idea_id, status, note="", on=None):
    if status not in IDEA_STATUS:
        raise Refused(f"status must be one of {', '.join(IDEA_STATUS)}")
    ideas, posts = store.ideas(), store.posts()
    idea = next((i for i in ideas if i["id"] == idea_id), None)
    if not idea:
        raise Refused(f"no idea {idea_id}")
    idea["status"] = status
    idea["history"].append({"on": today(on), "status": status, **({"note": note} if note else {})})
    if status in CONVERTED:                     # mark the insights as used, so they are not offered again
        for p in posts:
            if p["id"] in idea["insights"] and idea_id not in p["used_in"]:
                p["used_in"].append(idea_id)
        store.save_posts(posts)
    store.save_ideas(ideas)
    return idea


def score(idea):
    s = idea["scores"]
    raw = sum(WEIGHTS[f] * (6 - s[f] if f == "effort" else s[f]) for f in SCORE_FIELDS)
    return round((raw - 1) / 4 * 100, 1)       # 1..5 -> 0..100


def rank(ideas, n=5):
    done = [i for i in ideas if i["status"] in CONVERTED]
    out = []
    for i in ideas:
        if i["status"] not in OPEN:
            continue
        base = score(i)
        text = i["title"] + " " + i.get("angle", "")
        near = max(((similarity(text, d["title"] + " " + d.get("angle", "")), d["id"]) for d in done),
                   default=(0.0, None))
        penalty = 0.0
        why = []
        if near[0] >= 0.4:
            penalty += 25
            why.append(f"close to {near[1]}, already made")
        if i.get("recommended", 0):
            penalty += min(5 * i["recommended"], 20)
            why.append(f"recommended {i['recommended']}x before")
        bonus = 5 if i["status"] == "approved" else 0
        s = i["scores"]
        strengths = [f for f in ("relevance", "value", "originality", "confidence") if s[f] >= 4]
        if s["effort"] <= 2:
            strengths.append("quick to produce")
        out.append({"idea": i, "score": round(max(base - penalty + bonus, 0), 1), "base": base,
                    "strengths": strengths, "cautions": why})
    return sorted(out, key=lambda r: (-r["score"], r["idea"]["id"]))[:n]


def mark_recommended(store, ids, on=None):
    ideas = store.ideas()
    for i in ideas:
        if i["id"] in ids:
            i["recommended"] = i.get("recommended", 0) + 1
            i["last_recommended"] = today(on)
    store.save_ideas(ideas)


# ---------------------------------------------------------------------------
# digest
# ---------------------------------------------------------------------------
def fmt_metric(p, m):
    v = p["metrics"].get(m)
    if not v:
        return "-"
    return f"{v['value']:,}" + ("" if v["basis"] == "observed" else " (est.)")


def audience_questions(posts):
    """Questions from comments, merged when they differ only in case, spacing or end
    punctuation; most-asked first, then in capture order."""
    groups = {}
    for p in posts:
        for q in p.get("audience_questions", []):
            key = re.sub(r"[\s?!.।]+", " ", q.casefold()).strip()
            if key:
                g = groups.setdefault(key, [q.strip(), []])
                if p["id"] not in g[1]:
                    g[1].append(p["id"])
    return sorted(groups.values(), key=lambda g: -len(g[1]))


def digest(store, days=7, on=None, n=5, due_days=14):
    accounts, posts, ideas = store.accounts(), store.posts(), store.ideas()
    formulas = load_formulas(HOOKS) if load_formulas else None
    ref = today(on)
    since = (dt.date.fromisoformat(ref) - dt.timedelta(days=days)).isoformat()
    new = [p for p in posts if p["observed_on"] > since]
    active = [a for a in accounts if a["status"] == "active"]
    cand = [a for a in accounts if a["status"] == "candidate"]
    L = [f"# Research digest, {ref}", "",
         f"Window: the last {days} days. Archive: {len(active)} active accounts, {len(cand)} discovery "
         f"candidates, {len(posts)} posts, {len(ideas)} ideas.", ""]
    est = sum(1 for p in posts for v in p["metrics"].values() if v["basis"] == "estimate")
    L += ["Every number below was read off a post (observed) unless it says (est.). "
          f"{est} estimated values in the archive are shown but never used for rankings.", ""]
    due = due_accounts(accounts, due_days, on)
    L += [f"## Accounts due for a revisit (not researched in {due_days}+ days)", ""]
    L += [f"- {a['handle']} ({a['priority']}) - " + (f"last {a['last_researched']}" if a["last_researched"]
                                                      else "never researched") for a, _ in due] or ["- none"]
    L += ["", f"## New posts captured ({len(new)})", ""]
    for p in new[:15]:
        L.append(f"- {p['id']} {p['handle']} {p['format']}: \"{p.get('hook') or p.get('topic')}\" "
                 f"views {fmt_metric(p, 'views')}")
    if not new:
        L.append("- none. Research needs captured posts: see the /ig-viral skill for how to capture.")
    L += ["", "## Outliers (views over the account's own baseline, observed only)", ""]
    outl = outliers(accounts, posts, 1.5)
    L += [f"- {m:.1f}x {p['handle']} {p['id']}: \"{p.get('hook') or p.get('topic')}\" ({how})"
          for m, p, _, how in outl[:10]] or ["- none yet: an account needs an observed baseline (3+ posts "
                                             "with observed views, or baseline_views in the registry)"]
    tr = trends(posts, 30, on, formulas)
    L += ["", f"## Trends (last 30 days: {tr['recent_posts']} posts, the 30 before: {tr['prior_posts']})", ""]
    any_trend = False
    for dim, rows in tr["dimensions"].items():
        em = [r for r in rows if r["emerging"]]
        if em:
            any_trend = True
            L.append(f"- emerging {dim}: " + ", ".join(f"{r['value']} ({r['prior']} -> {r['recent']})" for r in em[:4]))
    if not any_trend:
        L.append("- nothing emerging: too few posts in the window to call a trend")
    asked = audience_questions(new)
    L += ["", f"## Audience questions (from comments on posts captured in the last {days} days)", ""]
    L += [f"- \"{q}\"" + (f" (asked on {len(ids)} posts)" if len(ids) > 1 else "") + f": {', '.join(ids[:5])}"
          for q, ids in asked[:15]] or ["- none captured in this window. Copy questions from comments, word for "
                                       "word, into audience_questions."]
    unused = [p for p in posts if not p["used_in"] and p.get("adaptable") in ("yes", "maybe")]
    L += ["", f"## Adaptable insights not yet used ({len(unused)})", ""]
    L += [f"- {p['id']} {p['handle']}: {p.get('adaptation') or p.get('hook') or p.get('topic')}"
          for p in unused[:10]] or ["- none"]
    counts = {s: sum(1 for i in ideas if i["status"] == s) for s in IDEA_STATUS}
    L += ["", "## Idea pipeline", "", "- " + ", ".join(f"{s} {c}" for s, c in counts.items() if c) if ideas else "- empty"]
    L += ["", f"## Recommended next ({min(n, len([i for i in ideas if i['status'] in OPEN]))})", ""]
    rec = rank(ideas, n)
    for r in rec:
        i = r["idea"]
        L.append(f"- **{i['id']} {i['title']}** ({i['format']}, score {r['score']}): "
                 + (", ".join(r["strengths"]) or "no standout strength")
                 + (f". Caution: {'; '.join(r['cautions'])}" if r["cautions"] else ""))
        for pid in i["insights"]:
            p = next((x for x in posts if x["id"] == pid), None)
            if p:
                L.append(f"  - from {pid} {p['handle']}: \"{p.get('hook') or p.get('topic')}\"")
    if not rec:
        L.append("- no open ideas. Turn an insight above into one with `research.py idea add`.")
    return "\n".join(L) + "\n", [r["idea"]["id"] for r in rec]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_table(rows, cols):
    if not rows:
        print("(none)")
        return
    widths = {c: min(max(len(c), *(len(str(r.get(c, ""))) for r in rows)), 40) for c in cols}
    print("  ".join(c.upper().ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, ""))[:40].ljust(widths[c]) for c in cols))


def build_parser():
    ap = argparse.ArgumentParser(description="Instagram research archive: accounts, posts, trends, ideas.")
    ap.add_argument("--data", help="archive folder (default $IG_RESEARCH_DIR or ~/.claude/instagram/research)")
    ap.add_argument("--today", help=argparse.SUPPRESS)          # fixed date, for tests
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")

    acc = sub.add_parser("account").add_subparsers(dest="sub", required=True)
    a = acc.add_parser("add")
    for f in ("handle", "name", "niche", "why", "priority", "notes", "baseline-views", "baseline-basis"):
        a.add_argument("--" + f, required=f == "handle")
    acc.add_parser("import").add_argument("file")
    li = acc.add_parser("list")
    li.add_argument("--due", type=int, help="only active accounts not researched in this many days")
    li.add_argument("--status")
    li.add_argument("--json", action="store_true")
    up = acc.add_parser("update")
    up.add_argument("handle")
    for f in ("name", "niche", "why", "priority", "status", "notes", "baseline-views", "baseline-basis"):
        up.add_argument("--" + f)
    d = acc.add_parser("done")
    d.add_argument("handle")
    d.add_argument("--on")

    dis = sub.add_parser("discover").add_subparsers(dest="sub", required=True)
    da = dis.add_parser("add")
    for f in ("handle", "name", "niche", "why", "found-via", "priority"):
        da.add_argument("--" + f, required=f in ("handle", "why", "found-via"))
    dis.add_parser("list")
    dis.add_parser("promote").add_argument("handle")
    dis.add_parser("reject").add_argument("handle")

    po = sub.add_parser("post").add_subparsers(dest="sub", required=True)
    po.add_parser("add").add_argument("--json", required=True)
    po.add_parser("import").add_argument("file")

    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--format")
    s.add_argument("--handle")
    s.add_argument("--since")
    s.add_argument("--json", action="store_true")
    o = sub.add_parser("outliers")
    o.add_argument("--min", type=float, default=1.0)
    t = sub.add_parser("trends")
    t.add_argument("--days", type=int, default=30)
    t.add_argument("--json", action="store_true")

    ide = sub.add_parser("idea").add_subparsers(dest="sub", required=True)
    ia = ide.add_parser("add")
    for f in ("title", "format", "angle", "audience", "pillar", "insights", "notes") + tuple(SCORE_FIELDS):
        ia.add_argument("--" + f, required=f in ("title", "format") + tuple(SCORE_FIELDS))
    ia.add_argument("--allow-duplicate", action="store_true")
    il = ide.add_parser("list")
    il.add_argument("--status")
    il.add_argument("--json", action="store_true")
    ist = ide.add_parser("status")
    ist.add_argument("id")
    ist.add_argument("status")
    ist.add_argument("--note", default="")

    r = sub.add_parser("recommend")
    r.add_argument("-n", type=int, default=5)
    r.add_argument("--mark", action="store_true", help="count this as a recommendation, to rotate repeats out")
    r.add_argument("--json", action="store_true")
    g = sub.add_parser("digest")
    g.add_argument("--days", type=int, default=7)
    g.add_argument("--due", type=int, default=14)
    g.add_argument("-n", type=int, default=5)
    g.add_argument("--save", action="store_true", help="write digests/<date>.md and mark the ideas recommended")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    store = Store(data_dir(args.data))
    on = args.today
    try:
        return run(args, store, on)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


def run(args, store, on):
    if args.cmd == "init":
        store.init()
        print(f"research archive ready at {store.root}")
        return 0
    if args.cmd == "status":
        acc, posts, ideas = store.accounts(), store.posts(), store.ideas()
        print(f"{store.root}: {sum(a['status'] == 'active' for a in acc)} active accounts, "
              f"{sum(a['status'] == 'candidate' for a in acc)} candidates, {len(posts)} posts, {len(ideas)} ideas")
        return 0
    if args.cmd == "account":
        if args.sub == "add":
            a = clean_account({"handle": args.handle, "name": args.name, "niche": args.niche, "why": args.why,
                               "priority": args.priority, "notes": args.notes,
                               "baseline_views": args.baseline_views, "baseline_basis": args.baseline_basis}, on=on)
            added, _ = upsert_accounts(store, [a])
            print(("added " if added else "updated ") + a["handle"])
            return 0
        if args.sub == "import":
            rows, bad = [], []
            for n, r in enumerate(read_table(args.file), 2):
                try:
                    rows.append(clean_account(r, on=on))
                except Refused as e:
                    bad.append(f"row {n}: {e}")
            added, updated = upsert_accounts(store, rows)
            print(f"imported {len(rows)} accounts: {added} new, {updated} updated"
                  + (f"; skipped {len(bad)} row(s)" if bad else ""))
            for b in bad:
                print("  skipped " + b)
            return 0
        if args.sub == "list":
            rows = store.accounts()
            if args.status:
                rows = [r for r in rows if r["status"] == args.status]
            if args.due is not None:
                rows = [a for a, _ in due_accounts(rows, args.due, on)]
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                print_table(rows, ["handle", "priority", "status", "niche", "last_researched", "baseline_views"])
                print(f"\n{len(rows)} account(s)")
            return 0
        if args.sub in ("update", "done"):
            rows = store.accounts()
            h = norm_handle(args.handle)
            row = next((r for r in rows if r["handle"] == h), None)
            if not row:
                raise Refused(f"{h} is not in the registry")
            if args.sub == "done":
                row["last_researched"] = args.on or today(on)
            else:
                for f in ("name", "niche", "why", "priority", "status", "notes", "baseline_views", "baseline_basis"):
                    v = getattr(args, f)
                    if v is not None:
                        row[f] = v
                row.update(clean_account(row, on=on))
            store.save_accounts(rows)
            print(f"{h} updated")
            return 0
    if args.cmd == "discover":
        rows = store.accounts()
        if args.sub == "add":
            a = clean_account({"handle": args.handle, "name": args.name, "niche": args.niche, "why": args.why,
                               "found_via": args.found_via, "priority": args.priority or "medium"},
                              source="discovered", status="candidate", on=on)
            existing = next((r for r in rows if r["handle"] == a["handle"]), None)
            if existing:
                print(f"{a['handle']} is already in the registry ({existing['status']}); nothing changed")
                return 0
            store.save_accounts(rows + [a])
            print(f"candidate {a['handle']} added. Check it on Instagram, then: discover promote {a['handle']}")
            return 0
        if args.sub == "list":
            print_table([r for r in rows if r["status"] == "candidate"], ["handle", "niche", "why", "found_via", "added"])
            return 0
        h = norm_handle(args.handle)
        row = next((r for r in rows if r["handle"] == h), None)
        if not row:
            raise Refused(f"{h} is not in the registry")
        row["status"] = "active" if args.sub == "promote" else "rejected"
        store.save_accounts(rows)
        print(f"{h}: {row['status']}")
        return 0
    if args.cmd == "post":
        if args.sub == "add":
            try:
                raws = [json.loads(args.json)]
            except json.JSONDecodeError as e:
                raise Refused(f"--json is not valid JSON: {e}")
        else:
            path = args.file
            if path.endswith(".jsonl"):
                raws = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
            else:
                raws = read_table(path)
        cleaned, skipped, unknown = add_posts(store, raws, on)
        print(f"added {len(cleaned)} post(s)" + (f": {', '.join(p['id'] for p in cleaned)}" if cleaned else "")
              + (f"; skipped {len(skipped)} already archived" if skipped else ""))
        if unknown:
            print(f"note: not in the registry yet: {', '.join(unknown)}. Add them with `account add` or "
                  "`discover add`.")
        return 0
    if args.cmd == "search":
        found = search(store.posts(), args.query, args.format, args.handle, args.since)
        if args.json:
            print(json.dumps(found, indent=2, ensure_ascii=False))
        else:
            for p in found:
                print(f"{p['id']}  {p['handle']:<22} {p['format']:<8} views {fmt_metric(p, 'views'):<12} "
                      f"{p.get('hook') or p.get('topic')}")
            print(f"\n{len(found)} match(es)")
        return 0
    if args.cmd == "outliers":
        rows = outliers(store.accounts(), store.posts(), args.min)
        for m, p, b, how in rows:
            print(f"{m:>6.1f}x  {p['id']}  {p['handle']:<22} {p['metrics']['views']['value']:>10,} vs {b:,} ({how})")
            print(f"         \"{p.get('hook') or p.get('topic')}\"")
        print(f"\n{len(rows)} post(s). Only observed views against an observed baseline are ranked.")
        return 0
    if args.cmd == "trends":
        formulas = load_formulas(HOOKS) if load_formulas else None
        tr = trends(store.posts(), args.days, on, formulas)
        if args.json:
            print(json.dumps(tr, indent=2, ensure_ascii=False))
            return 0
        print(f"last {args.days} days: {tr['recent_posts']} posts; the {args.days} before: {tr['prior_posts']}")
        for dim, rows in tr["dimensions"].items():
            print(f"\n{dim}")
            for r in rows[:8]:
                print(f"  {'EMERGING ' if r['emerging'] else '         '}{r['value']:<32} {r['prior']:>3} -> {r['recent']}")
        return 0
    if args.cmd == "idea":
        if args.sub == "add":
            fields = {f: getattr(args, f) for f in ("title", "format", "angle", "audience", "pillar", "notes")}
            fields.update({f: getattr(args, f) for f in SCORE_FIELDS})
            fields["insights"] = (args.insights or "").split(",") if args.insights else []
            fields["allow_duplicate"] = args.allow_duplicate
            i = add_idea(store, fields, on)
            print(f"{i['id']} added, score {score(i)}")
            return 0
        if args.sub == "status":
            i = set_status(store, args.id, args.status, args.note, on)
            print(f"{i['id']}: {i['status']}")
            return 0
        rows = store.ideas()
        if args.status:
            rows = [i for i in rows if i["status"] == args.status]
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            print_table([dict(i, score=score(i)) for i in rows], ["id", "status", "format", "score", "title"])
        return 0
    if args.cmd == "recommend":
        rec = rank(store.ideas(), args.n)
        if args.mark:
            mark_recommended(store, [r["idea"]["id"] for r in rec], on)
        if args.json:
            print(json.dumps(rec, indent=2, ensure_ascii=False))
            return 0
        for r in rec:
            i = r["idea"]
            print(f"{r['score']:>5}  {i['id']}  {i['format']:<8} {i['title']}")
            if r["strengths"]:
                print(f"       why: {', '.join(r['strengths'])}")
            if r["cautions"]:
                print(f"       caution: {'; '.join(r['cautions'])}")
        if not rec:
            print("no open ideas to recommend")
        return 0
    if args.cmd == "digest":
        text, ids = digest(store, args.days, on, args.n, args.due)
        if args.save:
            path = os.path.join(store.digests, f"{today(on)}.md")
            os.makedirs(store.digests, exist_ok=True)
            open(path, "w", encoding="utf-8").write(text)
            mark_recommended(store, ids, on)
            print(f"wrote {path}", file=sys.stderr)
        sys.stdout.write(text)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())

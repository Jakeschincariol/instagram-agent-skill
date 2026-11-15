#!/usr/bin/env python3
"""
content_calendar.py - the content calendar on top of the research archive: which idea
goes out on which day as which format, and what still stands between each
slot and publishing.

Slots are filled first with content already in production (ready, edited,
shot, scripted), then with the ideas the research engine ranks highest
(approved ideas; new ones too with --include-new). Every slot then passes the same gates, in order:

  idea      an idea is assigned
  package   a production package is attached (ig-reel/package.py --json, or a
            carousel slides file that passes ig-carousel/render.py --check)
  facts     every claim in the package is verified with a source
  approved  the creator approved it, recorded by hand with `approve`

The calendar never publishes and never approves on its own. `approve` only
records an approval the creator gives, and refuses while facts are unverified.

Usage
  content_calendar.py build --start 2026-11-17 --weeks 2 --cadence mon:reel,wed:carousel,fri:reel
  content_calendar.py show [--json]
  content_calendar.py attach 2026-11-17 --package package.json
  content_calendar.py approve 2026-11-17 --by "creator name"
  content_calendar.py check [--days 7]

Data: the same folder as research.py (--data, $IG_RESEARCH_DIR or
~/.claude/instagram/research), in calendar.json.
Exit status: 0 ok, 1 a gate is open (check) or a refusal, 2 bad usage.
"""

import argparse
import datetime as dt
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ig-viral"))
import research  # noqa: E402

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
GATES = ["idea", "package", "facts", "approved"]


class Refused(Exception):
    pass


def path(store):
    return os.path.join(store.root, "calendar.json")


def load(store):
    store.need()
    p = path(store)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"slots": []}


def save(store, cal):
    cal["slots"].sort(key=lambda s: s["date"])
    json.dump(cal, open(path(store), "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def parse_cadence(text):
    out = []
    for part in text.split(","):
        day, _, fmt = part.strip().partition(":")
        if day.lower()[:3] not in DAYS or fmt not in ("reel", "carousel"):
            raise Refused(f"cadence entries look like mon:reel or thu:carousel, not {part!r}")
        out.append((DAYS[day.lower()[:3]], fmt))
    return out


def build(store, start, weeks, cadence, include_new=False):
    cal = load(store)
    ideas = store.ideas()
    first = dt.date.fromisoformat(start)
    dates = []
    for w in range(weeks):
        monday = first - dt.timedelta(days=first.weekday()) + dt.timedelta(weeks=w)
        for wd, fmt in cadence:
            d = monday + dt.timedelta(days=wd)
            if d >= first:
                dates.append((d.isoformat(), fmt))
    taken = {s["idea_id"] for s in cal["slots"] if s.get("idea_id") and s["date"] not in {d for d, _ in dates}}
    # Content already in production goes first, furthest along first; then the
    # ranked open ideas (approved, plus new ones with --include-new).
    stage = {"ready": 0, "edited": 1, "shot": 2, "scripted": 3}
    in_production = sorted((i for i in ideas if i["status"] in stage), key=lambda i: (stage[i["status"]], i["id"]))
    pool = in_production + [r["idea"] for r in research.rank(ideas, n=len(ideas))
                            if r["idea"]["status"] == "approved" or include_new]
    slots = [s for s in cal["slots"] if s["date"] not in {d for d, _ in dates}]
    for d, fmt in sorted(dates):
        pick = next((i for i in pool if i["id"] not in taken and i["format"] in (fmt, "both")), None)
        slot = {"date": d, "format": fmt, "idea_id": "", "title": "", "package": "", "facts_ok": False,
                "ready": False, "approval": None}
        if pick:
            taken.add(pick["id"])
            slot.update(idea_id=pick["id"], title=pick["title"])
        slots.append(slot)
    cal["slots"] = slots
    save(store, cal)
    return cal


def find(cal, date):
    s = next((s for s in cal["slots"] if s["date"] == date), None)
    if not s:
        raise Refused(f"no slot on {date}. `content_calendar.py show` lists them")
    return s


def attach(store, date, package):
    cal = load(store)
    s = find(cal, date)
    if not os.path.exists(package):
        raise Refused(f"{package} does not exist")
    try:
        p = json.load(open(package, encoding="utf-8"))
    except json.JSONDecodeError:
        raise Refused("attach the JSON package: ig-reel/package.py spec.json --json -o package.json")
    claims = p.get("claims", [])
    s["package"] = os.path.abspath(package)
    s["facts_ok"] = all(c.get("status") == "verified" and c.get("source") for c in claims)
    s["ready"] = bool(p.get("ready", s["facts_ok"]))
    s["problems"] = p.get("problems", [])
    s["approval"] = None                     # a new package needs a new approval
    save(store, cal)
    return s


def gates(s):
    return {"idea": bool(s.get("idea_id")), "package": bool(s.get("package")),
            "facts": bool(s.get("facts_ok")), "approved": bool(s.get("approval"))}


def approve(store, date, by, on=None):
    cal = load(store)
    s = find(cal, date)
    g = gates(s)
    missing = [k for k in ("idea", "package", "facts") if not g[k]]
    if missing:
        raise Refused(f"{date} cannot be approved yet: {', '.join(missing)} not done")
    if not by.strip():
        raise Refused("say who approved it: --by NAME")
    s["approval"] = {"by": by.strip(), "on": research.today(on)}
    save(store, cal)
    return s


def render(cal, ideas):
    status = {i["id"]: i["status"] for i in ideas}
    L = ["| Date | Format | Idea | Idea status | Package | Facts | Approved |", "|---|---|---|---|---|---|---|"]
    for s in cal["slots"]:
        g = gates(s)
        tick = lambda b: "yes" if b else "no"
        L.append(f"| {s['date']} | {s['format']} | {(s['idea_id'] + ' ' + s['title']) if s['idea_id'] else 'OPEN: needs an idea'} "
                 f"| {status.get(s['idea_id'], '-')} | {tick(g['package'])} | {tick(g['facts'])} "
                 f"| {s['approval']['by'] + ' ' + s['approval']['on'] if s['approval'] else 'no'} |")
    return "\n".join(L) + "\n\nNothing here is published automatically. The creator publishes after approving.\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Content calendar and approval gates.")
    ap.add_argument("--data")
    ap.add_argument("--today", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--start", required=True)
    b.add_argument("--weeks", type=int, default=1)
    b.add_argument("--cadence", default="mon:reel,wed:carousel,fri:reel")
    b.add_argument("--include-new", action="store_true", help="also schedule ideas not yet approved")
    sh = sub.add_parser("show")
    sh.add_argument("--json", action="store_true")
    at = sub.add_parser("attach")
    at.add_argument("date")
    at.add_argument("--package", required=True)
    apv = sub.add_parser("approve")
    apv.add_argument("date")
    apv.add_argument("--by", required=True)
    c = sub.add_parser("check")
    c.add_argument("--days", type=int, default=7)
    args = ap.parse_args(argv)
    store = research.Store(research.data_dir(args.data))
    try:
        if args.cmd == "build":
            cal = build(store, args.start, args.weeks, parse_cadence(args.cadence), args.include_new)
            print(render(cal, store.ideas()))
        elif args.cmd == "show":
            cal = load(store)
            print(json.dumps(cal, indent=2, ensure_ascii=False) if args.json else render(cal, store.ideas()))
        elif args.cmd == "attach":
            s = attach(store, args.date, args.package)
            print(f"{s['date']}: package attached, facts {'verified' if s['facts_ok'] else 'NOT verified'}")
        elif args.cmd == "approve":
            s = approve(store, args.date, args.by, args.today)
            print(f"{s['date']}: approval recorded ({s['approval']['by']}, {s['approval']['on']}). "
                  "Publishing is still yours to do.")
        elif args.cmd == "check":
            ref = dt.date.fromisoformat(research.today(args.today))
            horizon = (ref + dt.timedelta(days=args.days)).isoformat()
            open_ = []
            for s in load(store)["slots"]:
                if ref.isoformat() <= s["date"] <= horizon:
                    missing = [g for g, ok in gates(s).items() if not ok]
                    if missing:
                        open_.append(s)
                        print(f"{s['date']} {s['format']:<8} {s['idea_id'] or 'OPEN':<7} waiting on: {', '.join(missing)}")
            print(f"{len(open_)} slot(s) in the next {args.days} days are not ready to publish")
            return 1 if open_ else 0
    except (Refused, research.Refused) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

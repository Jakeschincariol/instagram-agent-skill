#!/usr/bin/env python3
"""
package.py - turn a written Reel into a production package the creator can
shoot from: the hook scored, every scene timed, the shot list, B-roll, on-screen
text, edit rhythm, the caption linted, hashtags capped, and every factual
claim listed with its source.

The words are written by the model or the creator. This script checks and
assembles them. It does not shoot, record or publish anything: the package
ends with the approvals the creator gives by hand.

A package is READY only when every claim is verified, the caption is not FIX,
there is a hook, and every scene has voiceover and a shot. Otherwise it is
NOT READY, with the reasons.

Spec (JSON):
  {
    "title": "...", "idea_id": "i-0003", "why": "why this, now",
    "audience": "...", "target_seconds": 40, "wpm": 150,
    "hook": {"spoken": "...", "on_screen": "..."},
    "scenes": [{"voiceover": "...", "shot": "...", "broll": "...", "location": "...",
                "on_screen": "...", "transition": "cut"}],
    "caption": "...", "cta": "...",
    "hashtags": ["#a", "#b"],            or omit and pass --bank to pick them
    "topics": ["home loans"],            used to pick tags from the bank
    "keywords": ["..."],
    "claims": [{"claim": "...", "source": "...", "status": "verified" | "needs-check"}],
    "research_refs": ["p-0004"]
  }

Usage
  python3 package.py spec.json                    # markdown package to stdout
  python3 package.py spec.json -o package.md
  python3 package.py spec.json --bank hashtags.json
  python3 package.py spec.json --json

Exit status: 0 READY, 1 NOT READY (the package is still written), 2 bad spec.
"""

import argparse
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "ig-caption"))
import beats  # noqa: E402
import hookscore  # noqa: E402
try:
    import caption as caption_lint  # noqa: E402
except ImportError:                      # ig-reel copied without ig-caption
    caption_lint = None

HASHTAG_CAP = 5


class BadSpec(Exception):
    pass


def load(path):
    try:
        spec = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise BadSpec(f"cannot read {path}: {e}")
    for key in ("title", "hook", "scenes"):
        if not spec.get(key):
            raise BadSpec(f"spec needs {key!r}")
    if not isinstance(spec["scenes"], list):
        raise BadSpec("scenes must be a list")
    if isinstance(spec["hook"], str):
        spec["hook"] = {"spoken": spec["hook"]}
    return spec


def pick_hashtags(spec, bank):
    """The bank's always-tags, then the spec's own, then bank tags for the
    spec's topics, until there are five. Returns (tags, own): `own` is how many
    the spec asked for itself, which is the only count that can be too many."""
    own = [t if t.startswith("#") else "#" + t for t in spec.get("hashtags", [])]
    always = list((bank or {}).get("always", []))
    topical = [t for topic in spec.get("topics", []) for t in (bank or {}).get("topics", {}).get(topic, [])]
    seen, out = set(), []
    for t in always + own + topical:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    fixed = len({t.lower() for t in always + own})
    return out[:max(HASHTAG_CAP, fixed)], fixed


def build(spec, bank=None):
    problems = []
    hook = spec["hook"].get("spoken", "").strip()
    if not hook:
        problems.append("no spoken hook")
    script = "\n".join([hook] + [s.get("voiceover", "").strip() for s in spec["scenes"]])
    lang = beats.lang_of(script)
    wpm = spec.get("wpm") or (beats.WPM_EN if lang == "en" else beats.WPM_HI)
    wps = wpm / 60.0
    timing = beats.analyse(script, wpm=wpm, target=spec.get("target_seconds"))
    _, overall, verdict, flags = hookscore.run(hook) if hook else ({}, 0, "WEAK", [])

    rows, clock = [], len(beats.words(hook)) / wps
    rows.append({"n": 0, "start": 0.0, "dur": round(clock, 1), "voiceover": hook,
                 "shot": spec["hook"].get("shot", ""), "broll": spec["hook"].get("broll", ""),
                 "location": spec["hook"].get("location", ""), "on_screen": spec["hook"].get("on_screen", ""),
                 "transition": spec["hook"].get("transition", "")})
    for n, s in enumerate(spec["scenes"], 1):
        vo = s.get("voiceover", "").strip()
        dur = len(beats.words(vo)) / wps
        if not vo:
            problems.append(f"scene {n} has no voiceover")
        if not (s.get("shot") or s.get("broll")):
            problems.append(f"scene {n} has no shot or B-roll: say what to film")
        rows.append({"n": n, "start": round(clock, 1), "dur": round(dur, 1), "voiceover": vo,
                     "shot": s.get("shot", ""), "broll": s.get("broll", ""), "location": s.get("location", ""),
                     "on_screen": s.get("on_screen", ""), "transition": s.get("transition", "")})
        clock += dur
        if dur > beats.MAX_BEAT * 1.5:
            problems.append(f"scene {n} runs {dur:.1f}s with one shot: split it or cut B-roll inside it")

    claims = spec.get("claims", [])
    unverified = [c for c in claims if c.get("status") != "verified" or not c.get("source")]
    if unverified:
        problems.append(f"{len(unverified)} claim(s) not verified with a source")

    cap_text = spec.get("caption", "")
    tags, fixed = pick_hashtags(spec, bank)
    lint = None
    if cap_text and caption_lint:
        full = cap_text + ("\n\n" + " ".join(tags) if tags and "#" not in cap_text else "")
        lint = caption_lint.analyse(full, keywords=spec.get("keywords", []))
        if lint["verdict"] == "FIX":
            problems.append("caption lint says FIX")
    elif not cap_text:
        problems.append("no caption")
    if fixed > HASHTAG_CAP:
        problems.append(f"{fixed} hashtags asked for, Instagram counts at most {HASHTAG_CAP}")
    return {
        "title": spec["title"], "idea_id": spec.get("idea_id", ""), "why": spec.get("why", ""),
        "audience": spec.get("audience", ""), "language": lang, "wpm": wpm,
        "hook": {"spoken": hook, "on_screen": spec["hook"].get("on_screen", ""), "score": round(overall, 1),
                 "verdict": verdict, "flags": flags, "uncalibrated": lang != "en"},
        "total_seconds": round(clock, 1), "target_seconds": spec.get("target_seconds"),
        "timing_notes": timing["notes"] if timing else [],
        "scenes": rows, "caption": cap_text, "cta": spec.get("cta", ""), "hashtags": tags[:HASHTAG_CAP],
        "caption_lint": lint and {"verdict": lint["verdict"],
                                  "checks": [c for c in lint["checks"] if c["status"] != "PASS"]},
        "claims": claims, "research_refs": spec.get("research_refs", []),
        "ready": not problems, "problems": problems,
    }


def render(p):
    L = [f"# Reel package: {p['title']}", ""]
    L.append(f"**Status: {'READY to shoot' if p['ready'] else 'NOT READY'}**"
             + ("" if p["ready"] else " - " + "; ".join(p["problems"])))
    L += ["", f"- Idea: {p['idea_id'] or '-'}", f"- Why this, now: {p['why'] or '-'}",
          f"- Audience: {p['audience'] or '-'}",
          f"- Length: ~{p['total_seconds']}s at {p['wpm']:g} wpm"
          + (f" (target {p['target_seconds']}s)" if p["target_seconds"] else "")
          + f", language {p['language']}", ""]
    h = p["hook"]
    L += ["## Hook", "", f"- Spoken: {h['spoken']}", f"- On screen: {h['on_screen'] or '-'}",
          f"- Hook score: {h['score']} {h['verdict']}" + (" (uncalibrated for Hindi)" if h["uncalibrated"] else "")]
    L += [f"- Dealbreaker: {f}" for f in h["flags"]]
    L += ["", "## Scene by scene", "",
          "| # | Time | Voiceover | Shot | B-roll / location | On screen | Transition |",
          "|---|---|---|---|---|---|---|"]
    for r in p["scenes"]:
        cell = lambda s: (s or "-").replace("|", "/").replace("\n", " ")
        loc = " / ".join(x for x in (r["broll"], r["location"]) if x)
        L.append(f"| {'hook' if r['n'] == 0 else r['n']} | {r['start']:.1f}s +{r['dur']:.1f}s | {cell(r['voiceover'])} "
                 f"| {cell(r['shot'])} | {cell(loc)} | {cell(r['on_screen'])} | {cell(r['transition'])} |")
    if p["timing_notes"]:
        L += ["", "Edit notes from the beat sheet (beat 1 is the hook, beat 2 is scene 1):"] + [f"- {n}" for n in p["timing_notes"]]
    L += ["", "## Caption", "", p["caption"] or "(none)", "", f"- CTA: {p['cta'] or '-'}",
          f"- Hashtags ({len(p['hashtags'])}): {' '.join(p['hashtags']) or '-'}"]
    if p["caption_lint"]:
        L.append(f"- Caption lint: {p['caption_lint']['verdict']}")
        L += [f"  - {c['status']} {c['check']}: {c['detail']}" for c in p["caption_lint"]["checks"]]
    L += ["", "## Fact check", ""]
    if p["claims"]:
        L += ["| Claim | Source | Status |", "|---|---|---|"]
        L += [f"| {c.get('claim', '')} | {c.get('source') or 'MISSING'} | {c.get('status', 'needs-check')} |"
              for c in p["claims"]]
    else:
        L.append("No factual claims listed. If the script states a rate, a rule or a number, list it here.")
    if p["research_refs"]:
        L += ["", "Research: " + ", ".join(p["research_refs"])]
    L += ["", "## Approvals (by hand, in this order)", "",
          "- [ ] Facts checked against the sources above",
          "- [ ] Creator has shot the footage",
          "- [ ] Creator has recorded the voiceover",
          "- [ ] Creator has approved the final edit and caption",
          "- [ ] Creator has published it (this tool never publishes)", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Assemble and check a Reel production package.")
    ap.add_argument("spec")
    ap.add_argument("-o", "--out")
    ap.add_argument("--bank", help="hashtag bank JSON: {\"always\": [...], \"topics\": {topic: [...]}}")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        spec = load(args.spec)
        bank = json.load(open(args.bank, encoding="utf-8")) if args.bank else None
    except (BadSpec, OSError, json.JSONDecodeError) as e:
        print(f"bad spec: {e}", file=sys.stderr)
        sys.exit(2)
    p = build(spec, bank)
    text = json.dumps(p, indent=2, ensure_ascii=False) + "\n" if args.json else render(p)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    sys.exit(0 if p["ready"] else 1)


if __name__ == "__main__":
    main()

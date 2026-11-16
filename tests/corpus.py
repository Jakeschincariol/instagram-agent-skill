"""Every text used in the functional tests, for before/after verdict comparison."""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import outputs as o

def corpus():
    t = {
        "comment #3": o.COMMENTS[0][1], "comment #2": o.COMMENTS[1][1],
        "DM keyword": o.DM_KEYWORD, "DM +4d": o.DM_FOLLOWUPS[0][1], "DM +10d": o.DM_FOLLOWUPS[1][1],
        "bio": o.PROFILE_REWRITES["bio"], "carousel caption": o.CAROUSEL_CAPTION,
        "carousel slides": "\n".join(f"{h.title()}. {b}" for _, h, b in o.CAROUSEL),
        "story frames": "\n".join(f["says"] for f in o.STORY), "all replies": "\n".join(o.REPLIES.values()),
        "repurpose source": o.REPURPOSE_SOURCE,
        "H1a 4-of-5 comment": "I'd push back on mid-project raises. We tried it in 2023 with Northwind and it cost us "
                              "a $9,000 renewal that was otherwise fine. Next time I'd wait.",
        "run-on 1 sentence": "We spent the whole of last quarter rebuilding the proposal template from scratch because "
                             "the old one kept losing deals to agencies that answered pricing questions on page one "
                             "and we finally copied them",
    }
    for f in ("draft.txt", "clean.txt", "clean4.txt", "round2.txt", "round2_clean.txt", "script.txt", "url.txt",
              "cap_good.txt", "cap_fixed.txt", "cap_bad.txt", "story.txt"):
        t[f] = open(os.path.join(HERE, f), encoding="utf-8").read()
    for r in o.REPLIES:
        t["reply " + r] = o.REPLIES[r]
    return t

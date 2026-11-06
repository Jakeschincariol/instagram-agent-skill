#!/usr/bin/env python3
"""
Every formula in hooks.json ships with an `example`: the line that formula is
for. That example is the one hook in the world we know the right answer for, so
it is also the cheapest possible test of the `match` regex beside it.

This runs the example through the same classifier `/ig-viral` uses - same
classify_order, same first-match-wins, same IGNORECASE - and checks each one
comes back as its own formula.

It is a regex test, not a taste test. It cannot tell you whether a formula is
worth having. It tells you whether the pattern recognises the line the pack
itself put forward as the canonical case, which is the floor, not the ceiling.

    python3 tests/test_hook_formulas.py
    python3 tests/test_hook_formulas.py --verbose

Exits non-zero if any example fails to classify as itself.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..", "skills", "ig-reel", "hooks.json")


def load(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    hooks = doc if isinstance(doc, list) else doc.get("hooks", doc)
    by_id = {h["id"]: h for h in hooks}
    order = (doc.get("classify_order") if isinstance(doc, dict) else None) or sorted(by_id)
    return hooks, by_id, order


def compile_all(by_id, order):
    """Same shape as swipe.py: ordered, IGNORECASE, first match wins."""
    out = []
    for i in order:
        if i not in by_id:
            continue
        try:
            out.append((i, by_id[i]["name"], re.compile(by_id[i]["match"], re.IGNORECASE)))
        except re.error as err:
            print("  BROKEN REGEX  #%s %s: %s" % (i, by_id[i]["name"], err))
            raise SystemExit(2)
    return out


def classify(hook, formulas):
    for fid, name, pattern in formulas:
        if pattern.search(hook):
            return fid, name
    return None, "unclassified"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="print every formula, not just failures")
    ap.add_argument("--hooks", default=HOOKS, help="path to hooks.json")
    args = ap.parse_args()

    hooks, by_id, order = load(args.hooks)
    formulas = compile_all(by_id, order)

    missing = [h["id"] for h in hooks if not h.get("example")]
    tested = [h for h in hooks if h.get("example")]

    failures = []
    for h in tested:
        got_id, got_name = classify(h["example"], formulas)
        ok = got_id == h["id"]
        if not ok:
            failures.append((h, got_id, got_name))
        if args.verbose or not ok:
            flag = "ok  " if ok else "FAIL"
            print("  %s #%-2s %-28s -> %s" % (flag, h["id"], h["name"], got_name))
            if not ok:
                print("       example: %s" % h["example"])
                print("       match:   %s" % h["match"][:140])

    print()
    print("%d of %d examples classify as their own formula" % (len(tested) - len(failures), len(tested)))
    if missing:
        print("%d formula(s) have no example and were not tested: %s"
              % (len(missing), ", ".join("#%s" % i for i in missing)))

    if failures:
        print()
        print("A formula that cannot recognise its own example will not recognise")
        print("a real hook either. /ig-viral will file those rows as unclassified.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

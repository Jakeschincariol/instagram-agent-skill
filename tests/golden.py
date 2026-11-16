#!/usr/bin/env python3
"""English golden snapshots: the exact output of the 6 skill scripts on the
English fixtures, captured byte for byte.

  python3 tests/golden.py --check     # compare current output with tests/golden/
  python3 tests/golden.py --update    # (re)write tests/golden/ from current output

Each case runs the script as a subprocess, from this folder, with relative
fixture paths, so the output contains no machine-specific paths. A difference
in stdout or exit code fails --check. Later phases must keep these identical
for English input unless a change is intended and approved.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("IG_SKILLS_ROOT") or os.path.dirname(HERE)
SK = os.path.join(REPO, ".claude", "skills")
GOLD = os.path.join(HERE, "golden")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

CASES = [
    # (name, script, args)
    ("detect__draft", "ig-human/detect.py", ["draft.txt", "--json"]),
    ("detect__clean", "ig-human/detect.py", ["clean.txt", "--json"]),
    ("detect__clean4", "ig-human/detect.py", ["clean4.txt", "--json"]),
    ("detect__round2", "ig-human/detect.py", ["round2.txt", "--json"]),
    ("detect__round2_clean", "ig-human/detect.py", ["round2_clean.txt", "--json"]),
    ("detect__url", "ig-human/detect.py", ["url.txt", "--json"]),
    ("detect__cap_bad", "ig-human/detect.py", ["cap_bad.txt", "--json"]),
    ("detect__story", "ig-human/detect.py", ["story.txt", "--json"]),
    ("detect__compare_draft_round2", "ig-human/detect.py", ["draft.txt", "round2_clean.txt", "--json"]),
    ("detect__text_draft_round2", "ig-human/detect.py", ["draft.txt", "round2_clean.txt"]),
    ("humanize__draft", "ig-human/humanize.py", ["draft.txt", "--json"]),
    ("humanize__clean", "ig-human/humanize.py", ["clean.txt", "--json"]),
    ("humanize__url", "ig-human/humanize.py", ["url.txt", "--json"]),
    ("humanize__cap_bad", "ig-human/humanize.py", ["cap_bad.txt", "--json"]),
    ("hookscore__readme_hooks", "ig-reel/hookscore.py", ["readme_hooks.txt", "--json"]),
    ("hookscore__readme_hooks_text", "ig-reel/hookscore.py", ["readme_hooks.txt"]),
    ("beats__script", "ig-reel/beats.py", ["script.txt", "--json"]),
    ("beats__script_target30", "ig-reel/beats.py", ["script.txt", "--target", "30"]),
    ("caption__fixed_kw", "ig-caption/caption.py", ["cap_fixed.txt", "--keywords", "client proposals,proposal template", "--json"]),
    ("caption__fixed_text", "ig-caption/caption.py", ["cap_fixed.txt", "--keywords", "client proposals,proposal template"]),
    ("caption__bad", "ig-caption/caption.py", ["cap_bad.txt", "--json"]),
    ("caption__good", "ig-caption/caption.py", ["cap_good.txt", "--json"]),
    ("swipe__captured", "ig-viral/swipe.py", ["captured.tsv", "--json"]),
    ("swipe__captured_text", "ig-viral/swipe.py", ["captured.tsv"]),
]


def run(script, args):
    p = subprocess.run([sys.executable, os.path.join(SK, script), *args],
                       capture_output=True, text=True, env=ENV, cwd=HERE)
    return {"cmd": [script, *args], "exit": p.returncode, "stdout": p.stdout}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode not in ("--check", "--update"):
        sys.exit("usage: golden.py --check | --update")
    os.makedirs(GOLD, exist_ok=True)
    bad = 0
    for name, script, args in CASES:
        cur = run(script, args)
        path = os.path.join(GOLD, name + ".json")
        if mode == "--update":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cur, f, ensure_ascii=False, indent=1)
                f.write("\n")
            print(f"WROTE {name}")
            continue
        if not os.path.exists(path):
            print(f"MISSING {name}"); bad += 1; continue
        want = json.load(open(path, encoding="utf-8"))
        if want != cur:
            bad += 1
            what = "exit code" if want["exit"] != cur["exit"] else "stdout"
            print(f"CHANGED {name} ({what})")
        else:
            print(f"SAME    {name}")
    if mode == "--check":
        print(f"\n{len(CASES) - bad} unchanged, {bad} changed or missing (of {len(CASES)})")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

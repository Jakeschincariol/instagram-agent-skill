#!/usr/bin/env python3
"""Run every test layer and print a one-screen summary. Exit 0 only if all pass.

  python3 tests/run_all.py
  IG_SKILLS_ROOT=/path/to/instagram-agent-skill python3 tests/run_all.py
"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(name, args):
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=ENV, cwd=HERE)
    return p.returncode, p.stdout + p.stderr


ok = True
rc, out = run("regression", ["regress.py"])
fails = [l for l in out.splitlines() if l.startswith("FAIL")]
summary = (re.findall(r"\d+ passed, \d+ failed", out) or ["no summary"])[-1]
print(f"regression : {summary}")
for l in fails:
    print("   " + l)
ok &= rc == 0 and not fails

rc, out = run("hindi", ["hindi.py"])
fails = [l for l in out.splitlines() if l.startswith("FAIL")]
summary = (re.findall(r"\d+ passed, \d+ failed", out) or ["no summary"])[-1]
print(f"hindi      : {summary}")
for l in fails:
    print("   " + l)
ok &= rc == 0 and not fails

rc, out = run("functional", ["validate.py"])
counts = re.findall(r"^(ig-[a-z]+): (\d+)/(\d+) checks pass", out, re.M)
passed = sum(int(a) for _, a, _ in counts); total = sum(int(b) for _, _, b in counts)
print(f"functional : {passed}/{total} checks across {len(counts)} skills")
for l in out.splitlines():
    if l.strip().startswith("FAIL"):
        print("   " + l.strip())
ok &= rc == 0 and passed == total and total > 0

rc, out = run("golden", ["golden.py", "--check"])
print("golden     : " + (out.strip().splitlines() or ["no output"])[-1])
for l in out.splitlines():
    if l.startswith(("CHANGED", "MISSING")):
        print("   " + l)
ok &= rc == 0

print("\nALL PASS" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)

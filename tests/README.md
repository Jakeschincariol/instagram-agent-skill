# Tests

Four layers, all plain Python 3 standard library (no pytest, no extra packages).
Tested with **Python 3.13**, the version CI uses.

| Layer | File | What it checks | Expected |
|---|---|---|---|
| Regression | `regress.py` | 70 tests on the skill scripts (humanize, detect, caption, hookscore, beats, swipe) and the docs they depend on | 70 passed, 0 failed |
| Hindi | `hindi.py` | 38 tests on Hindi and mixed Hindi-English text: tokenizer and language detection, spelling variants, Hindi hooks, beats timing, caption asks, detection, joiners, formulas; the corrections from the native-language review (M1-M13); and that English output gains no new fields | 38 passed, 0 failed |
| Functional | `validate.py` | 90 checks: sample outputs for 9 instruction-only skills against each SKILL.md's own rules, plus `/ig-human` scoring | 90/90 |
| Golden | `golden.py --check` | Exact English output (stdout + exit code) of the scripts on the English fixtures | 24/24 unchanged |

## Run

From the repository root:

```bash
python3 tests/run_all.py             # everything, one summary, exit 0 = all pass
```

Individually:

```bash
python3 tests/regress.py                          # all 70
python3 tests/regress.py H C                      # only ids starting with H or C
python3 tests/hindi.py                            # all 38 Hindi tests
PYTHONDONTWRITEBYTECODE=1 python3 tests/validate.py
python3 tests/golden.py --check
```

By default the tests run against the skills in this repository
(`.claude/skills/`). To test another checkout instead:

```bash
IG_SKILLS_ROOT=/path/to/other/checkout python3 tests/run_all.py
```

## CI

`.github/workflows/tests.yml` runs `python3 tests/run_all.py` on Python 3.13
for every pull request and every push to `main`. A non-zero exit fails the check.

## Golden snapshots

`golden/*.json` record the English output of the scripts at the commit the
suite was added. English output must stay identical. Only regenerate with
`python3 tests/golden.py --update` when a change is intended and approved,
and show the before/after diff in the pull request.

## Files

- Fixtures: `draft.txt`, `clean.txt`, `clean4.txt`, `round2.txt`, `round2_clean.txt`,
  `script.txt`, `url.txt`, `cap_good.txt`, `cap_fixed.txt`, `cap_bad.txt`, `story.txt`,
  `readme_hooks.txt`, `captured.tsv`, `verdicts_before.json`
- Hindi and mixed fixtures in `hi/`: `hooks.txt`, `script.txt` (exactly 100 words),
  `caption_mixed.txt`, `caption_greeting.txt`, `draft_hi.txt`, `human_hi.txt`,
  `joiners.txt`, `mixed_delete.txt`, `swipe.tsv`
- Sample outputs and corpora: `outputs.py`, `corpus.py`, `dm_fills.py`

All people, handles, numbers and links in the fixtures, English and Hindi, are fictional (the
persona "Dana", invented accounts, `example.com` addresses).

- Generated while running and git-ignored: `swipe_local.md`, `ok.txt`, `solo_beats/`, `__pycache__/`

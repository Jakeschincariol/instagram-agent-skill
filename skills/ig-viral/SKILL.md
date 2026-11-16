---
name: ig-viral
description: >-
  Go and find the reels that are actually working right now in the user's
  niche, rank them by how far each beat its own account, name the hook formula
  each one used, and turn that into a swipe file they can shoot from. Use when
  the user says "find viral videos", "what's working right now", "what are
  people posting in my niche", "reverse engineer this account", "build me a
  swipe file", "why is this reel doing numbers", or asks what to make next and
  has no evidence to answer with.
---

# ig-viral

The research skill. Everything else in this pack writes; this one goes and
looks. Run it monthly, not daily. Formulas last a season.

One tool lives in this folder and it runs:

```bash
python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
```

## The one idea that makes this worth doing

**Raw views are not evidence.** An account with two million followers doing
400,000 views had a quiet Tuesday. An account with four thousand followers
doing 400,000 views found something, and that something is copyable.

So everything here ranks on the **outlier multiple**: views divided by that
account's own recent median. Anything above 3x is a signal. Anything below 1.5x
is that account's normal day and it teaches you nothing, no matter how big the
number looks.

Collect accounts **within about 10x of the user's own size**. A formula that
works at 2M followers often works because it is at 2M followers.

## Step 1: pick the accounts

Ask the user for 6 to 12 accounts, or propose them and get approval:

- **4 direct** - same niche, same offer, slightly ahead.
- **4 adjacent** - different niche, same audience. This is where formats get
  borrowed from before anybody in the niche has them.
- **2 to 4 outsized** - much bigger accounts, for format only, never for
  cadence or tone.

Also ask them to open their own **Saved collection**. It is the fastest and
most relevant corpus that exists and it is already filtered by their taste.

## Step 2: go and look

Use whatever browsing tool this session actually has: an in-app browser, a
browser extension connected to the user's own Chrome, or a computer-use tool.
There is no API for this and there does not need to be, because the volume is
small enough to read.

**Rules that are not negotiable:**

- **Never log into Instagram on the user's behalf and never ask for a
  password.** If a page needs a login, the user is the one who is already
  logged in. Drive their browser with them present, or ask them to paste.
- **This is reading, not scraping.** Ten accounts, a dozen reels each, at human
  speed. Automated collection at volume violates Instagram's Terms of Use and
  gets accounts action-blocked. Do not build a crawler, do not use a scraping
  service, and do not loop this in the background.
- **Copy the formula, never the video.** The hook shape, the structure, the
  length, the pattern of cuts. Not their script, not their voice, not their
  edit. Attribute every row in the swipe file to the account it came from.

**What to capture per reel**, in the creator's own words:

| field | notes |
| --- | --- |
| account | handle |
| followers | from the profile |
| median | eyeball the last 12 reels and take the middle view count |
| views | this reel |
| hook | the first line, spoken or on screen, verbatim including bad grammar |
| on-screen | the first text card, if different |
| length | seconds |
| cta | what they asked for at the end |

Median is the important one. Without it you are back to ranking by follower
count, which is the thing this skill exists to stop.

**When Instagram will not show you enough:** the same hook grammar runs on
YouTube Shorts, where view counts and transcripts are public and no login is
involved. It is a legitimate second corpus, and the spoken hook is easier to
get:

```bash
# view counts for a channel's shorts
python3 -m yt_dlp --flat-playlist --playlist-end 40 -J \
  "https://www.youtube.com/@HANDLE/shorts" > channel.json

# the spoken first line of one short, from its auto-captions
python3 -m yt_dlp --skip-download --write-auto-subs --sub-langs "en.*" \
  --sub-format json3 -o hook "https://www.youtube.com/watch?v=VIDEO_ID"
```

Take every caption word with a timestamp under 3.0 seconds. That is the hook,
as said, not as written.

These two commands need `yt-dlp`, the one optional dependency in the pack. It
is not installed by default; if `python3 -m yt_dlp` says "No module named
yt_dlp", install it with `pip install yt-dlp`, or skip this step and use what
you captured by hand. `swipe.py` itself needs nothing beyond Python 3.

## Step 3: rank it

Fill a tab-separated file with a header row and run the script:

```
account	followers	median	views	hook	on-screen	length	cta
@someone	48000	11000	412000	nobody tells you your first 30 reels are supposed to flop	FIRST 30 FLOP	24	comment FLOP
```

`views` and `hook` are required. `on-screen`, `length` (seconds) and `cta` are
optional; when they are there, the script compares them between the top and
bottom thirds (median length, which asks, how many had a text card).

```bash
python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
```

It computes the outlier multiple, names the hook formula using the same 26
formulas `/ig-reel` writes from, scores each hook with `hookscore.py`, and
prints what separates the top third from the bottom third: hook score, hook
length, and, from the optional columns, reel length, the ask and the on-screen
card. Whether the payoff is visual and whether the first frame moves are not in
the file; read those off the reels yourself.

## Step 4: say what it means, carefully

Report three things and no more:

1. **Which formulas over-index** in the top third, with counts. Two formulas
   appearing four times each across six accounts is a finding. One appearing
   twice is not.
2. **What the top third have in common structurally** that the bottom third do
   not: hook length, whether the payoff is visual, whether the first frame
   moves, where the ask is.
3. **The unclassified rows.** Every hook the classifier could not name is
   either noise or a formula that is not in `hooks.json` yet. Read them by
   hand. This is the most valuable column in the output and it is the reason
   the script prints the count.

Then state the sample size and the confidence in plain words. Forty reels
across six accounts supports a claim. Twelve does not, and saying so is the
difference between research and horoscopes.

## Step 5: turn it into something to shoot

For the top three formulas, write **the user's version**: their own story,
their own number, in the shape that is working. Hand each one to `/ig-reel`
with the formula id already chosen.

Never hand back "make a reel like this one". Hand back a hook line they could
say tomorrow.

## Output

```
SWIPE  ·  38 reels  ·  7 accounts  ·  baseline: account median

OUTLIERS (above 3x)
  38.4x  hook 86  #3  Nobody Tells You   @acct_a    412,000  (median 10,700)
  11.2x  hook 79  #9  The Steal          @acct_c    180,000  (median 16,100)
  ...

WHAT IS OVER-INDEXING
  #3 Nobody Tells You   x5 in the top third, 0 in the bottom
  #2 Negative Command   x4
  median hook length    8 words up top, 19 at the bottom

UNCLASSIFIED (6)
  Two of these are the same shape and it is not in hooks.json: a hook that
  opens on someone else's comment read out loud. Worth adding.

YOUR VERSION
  #3  "Nobody tells you the first 20 proposals are supposed to lose."
  ...
```

Write the swipe file to `~/.claude/instagram/swipe.md`. `/ig-reel` and
`/ig-plan` both read it, which is the point: after this runs once, the rest of
the pack is working from the user's own evidence instead of from defaults.

Nothing is posted, followed, liked or messaged by this skill. It reads.

## Hindi hooks

`swipe.py` counts Hindi words in a hook and names its formula from `match_hi` in
`ig-reel/hooks.json` when the hook has Devanagari in it; English hooks are named exactly as
before. Rows with Hindi carry `"lang"` in the JSON, and their hook scores are uncalibrated (see
`ig-reel/SKILL.md`). A Hindi hook that matches no formula is a reason to read it by hand, the
same as an English one.

## The research archive (`research.py`)

`swipe.py` ranks one batch. `research.py` keeps the evidence between batches, so
research compounds instead of starting over: the accounts you watch, every post
you captured, what is trending across them, and which ideas came out of it.

```bash
R="python3 research.py --data PATH"          # or set IG_RESEARCH_DIR once
$R init
$R account add --handle @someone --name "..." --niche "..." --why "..." --priority high
$R account import accounts.tsv               # the user's list, any length
$R account list --due 14                     # who has not been researched in 14 days
$R discover add --handle @new --why "..." --found-via "where you found it"
$R discover promote @new                     # after the user has checked it is real
$R post import captured.tsv                  # what was seen, with views_basis per number
$R account done @someone                     # mark an account researched today
$R outliers --min 2                          # posts at 2x+ their own account's baseline
$R trends --days 30                          # emerging formulas, formats, categories, styles
$R search "home loan" --format carousel
$R idea add --title "..." --format reel --insights p-0004 --relevance 5 --originality 4 --value 5 --confidence 3 --effort 2
$R recommend -n 5 --mark
$R idea status i-0003 scripted               # its insights are marked used
$R digest --days 7 --save                    # the regular research digest
```

Rules the archive enforces, so the skill does not have to remember them:

- **No number without a basis.** Every metric is `observed` (read off the post)
  or `estimate`, and a metric with neither is refused. Estimates are shown and
  never used to rank. Counts are kept as the post shows them: `12.4K`,
  `1.2M` and `1.5 lakh` are parsed (12400, 1200000, 150000) and keep the
  label as `shown`; anything else is refused, never cut to its digits.
- **One post, one record.** URLs are stored in one form (no `?igsh=`, `/reel/`
  for reels), and a post already archived under any URL form is skipped.
- **Captured fields are kept**, including `caption`, `posted_on` (the date on
  the post), `slides` (carousels) and `duration_s` (reels). The digest lists
  the audience questions copied from comments, merged and counted.
- **Outliers are relative.** A post is ranked against its own account's
  observed baseline (registry `baseline_views` or the median of 3+ archived
  posts), never on raw views.
- **Discovery is a queue, not a registry.** Discovered accounts stay
  `candidate` until someone has checked them on Instagram and promoted them.
- **Ideas are not repeated.** A near-duplicate idea is refused; ideas close to
  something already made, or recommended before, sink in the ranking; an
  insight turned into content is marked used.
- **It does not fetch Instagram.** Capture happens in the user's own logged-in
  browser at human pace, or in an authorised browser session. A digest run
  without new captures says so.

Ranking: relevance 30%, audience value 25%, originality 20%, research
confidence 15%, ease of production 10%, each scored 1 to 5 by the person
adding the idea; approved ideas get a small lift.

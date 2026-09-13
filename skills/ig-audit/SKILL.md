---
name: ig-audit
description: >-
  Post-mortem on what the user has already posted - which reels actually
  worked, why, and what to stop making. Use when the user pastes their
  Instagram insights or past posts and asks "what's working", "why did this
  flop", "read my analytics", "audit my content", or wants to know what to do
  more of.
---

# ig-audit

The only honest source of what works for an account is that account. Every
rule in every Instagram guide, including the ones in this pack, is a prior.
The user's own last 30 posts are the evidence.

## Input

Ask for whichever the user has:

- Insights per post: views, reach, interactions, watch time, saves, shares,
  follows, and the non-follower share of reach. Screenshots are fine.
- Or the retention graph for their best and worst recent reels. This one
  screenshot is worth more than the rest combined.
- Or just the posts and their view counts, which is enough for a first pass.

Also read `~/.claude/instagram/log.md` if it exists, since it records which
hook formula each post used.

## What to actually measure

Raw views is the least useful number on the page, because it is mostly a
function of how many people already follow the account. Compute these instead
and show the working:

| metric | how | what it tells you |
| --- | --- | --- |
| **Outlier multiple** | views / the account's own median views | whether this was a real hit or a normal day |
| **Non-follower reach** | % of reach from people who do not follow | whether it travelled at all |
| **Hold at 3s** | viewers still there at 3s / viewers who started | whether the hook worked. This is the hook's grade. |
| **Average watch time** | straight from insights | whether the middle worked |
| **Sends per reach** | shares / reach | the strongest single signal you can earn. A send is a person putting their name on it. |
| **Follows per reach** | follows / reach | whether the profile converted the attention |

Rank by outlier multiple and sends per reach, not views. A reel with 4,000
views and 90 sends beat the one with 60,000 views and 11.

## Then find the pattern

With the top five and bottom five side by side, look for what separates them,
and be willing to conclude something the user will not like:

- **Hold at 3 seconds.** If the top and bottom differ here, it is the hook and
  nothing else, and everything downstream is a distraction.
- **Hook formula.** Which ids from `ig-reel/hooks.json` are in the top five?
- **Format.** Reel, carousel, single image.
- **Length.** Group into under 15s, 15 to 30s, 30 to 60s, over 60s.
- **Theme.**
- **Whether the user replied to comments in the first hour.**
- **Day and time.** Check this **last** and only if the others show nothing.
  It is almost never the cause and it is where people want it to be.

State the finding as a claim with the evidence attached, and say how confident
it is. With 30 posts you can see a pattern. With 6 you cannot, and saying so is
better than inventing one.

## The distinction that saves people months

**A reel that gets views and no follows is not a failed reel, it is a profile
problem.** A reel that gets no views is a hook problem. Separate the two before
recommending anything. If non-follower reach is high and follows per reach is
low, stop rewriting hooks and go to `/ig-profile`.

## Output

```
AUDIT  ·  31 posts  ·  Jun 12 - Sep 5  ·  median views 4,100

TOP 5 BY OUTLIER MULTIPLE
  18.2x  #3  Nobody Tells You   74,600 views  62% non-follower  hold@3s 71%  128 sends
   6.4x  #1  Cost Confession    26,300 views  48% non-follower  hold@3s 64%   71 sends
  ...

BOTTOM 5
   0.3x  #11 Numbered            1,200 views  9% non-follower   hold@3s 31%    2 sends
  ...

WHAT THE DATA SAYS
1. Hold at 3 seconds is the whole story. Top five average 66%, bottom five 33%.
   Everything else you are worried about is downstream of the first two seconds.
2. The posts where you were the one who looked bad: mean 8.1x vs 0.9x for
   everything else. n=5. Strongest signal here and it is not close.
3. Tool listicles get views and nothing else. High reach, no sends, no follows.
   Three of your bottom five.
4. Day of week shows nothing. Your Tuesday and Friday means are inside the
   noise. Stop optimising it.

STOP: listicles.
DO MORE: the ones with a cost you paid and a number attached.
```

Then hand the conclusions to `/ig-plan` so next week is built on the user's own
evidence rather than on defaults, and to `/ig-viral` so the swipe file gets
filtered to the formulas that work for this account specifically.

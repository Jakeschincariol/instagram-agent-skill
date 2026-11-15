# Outputs produced by following each instruction-only SKILL.md on a realistic
# input. Persona for all tests: Dana, @dana.proposals, runs a 4-person design
# agency and sells a $49 proposal template to freelancers and small agencies.

HANDLE = "@dana.proposals"

# ---------------------------------------------------------------- ig-carousel
CAROUSEL_INPUT = "Turn this into a carousel: the four clauses I now put in every client contract after a client clawed back $18,000."
CAROUSEL = [
    ("COVER", "THE $18,000 CLAUSE", "Four lines I now put in every contract."),
    ("STAKE", "SHE APPROVED IT. THEN REFUNDED.", "I approved the work. They asked for the money back nine days later."),
    ("", "PAYMENT ON DELIVERY", "Not on approval. Approval is a feeling. Delivery is a date you can point to."),
    ("", "TWO ROUNDS OF EDITS", "Round three is billed at the day rate. Write the number in, or it never gets charged."),
    ("", "A 30% KILL FEE", "If they cancel after kickoff, 30% is due. I've never invoiced it. Everyone reads it."),
    ("", "LATE FEEDBACK MOVES DEADLINES", "Feedback after five business days moves the deadline by the same amount."),
    ("RECAP", "ALL FOUR, IN ORDER", "1. Payment on delivery. 2. Two rounds. 3. 30% kill fee. 4. Late feedback moves the date."),
    ("CTA", "WANT THE EXACT WORDING?", "Comment CLAUSE and I'll send you all four, word for word."),
]
CAROUSEL_CAPTION = """A client approved the work, then asked for $18,000 back nine days later.

The contract said payment on approval. That one word was the whole problem, and it's the first thing I changed.

These are the client contracts clauses I've put in every agreement since, and every freelance contracts template I sell. None of them are aggressive. They just move the money off a feeling and onto a date.

Comment CLAUSE and I'll send the exact wording.

#freelancecontracts #agencyowner #clientcontracts
"""
CAROUSEL_ALT = "Bold black text on a cream background reading THE $18,000 CLAUSE, with a smaller line underneath: four lines I now put in every contract."

# -------------------------------------------------------------------- ig-story
STORY_INPUT = "What do I post on my story today? I just sent a proposal using my template and want to sell it without making a post."
STORY = [
    {"frame": 1, "visual": "selfie, walking to the studio", "says": "Sent a proposal in 20 minutes this morning. It used to eat 5 hours of my Tuesday and I'd still send it late.", "sticker": None},
    {"frame": 2, "visual": "screen recording of the template", "says": "This is the bit that does it. 6 questions on page 1.", "sticker": None},
    {"frame": 3, "visual": "talking to camera", "says": "Scope, price, what's out. Nobody has to hunt for it.", "sticker": None},
    {"frame": 4, "visual": "photo of laptop", "says": "How long does your last proposal take you?", "sticker": "poll: Under an hour / Half a day+"},
    {"frame": 5, "visual": "text on photo of the desk", "says": "If you voted half a day, reply and I'll send you page one.", "sticker": None},
]
STORY_AFTER = "Everyone who votes 'Half a day+' gets a personal reply with page one. They moved first, so that's a reply, not outreach."

# ------------------------------------------------------------------ ig-comment
COMMENT_INPUT = "@pricingpaul reel: 'Raise your prices mid-project. Clients respect confidence, and the ones who leave were never going to pay you properly anyway.'"
COMMENTS = [
    ("3 · Respectful disagree", "Agree the ones who leave over price were rarely great clients. Mid-project is where I'd push back: we tried it in 2023 and lost a renewal that was otherwise fine."),
    ("2 · Add the missing case", "This holds until the scope was fixed in writing. Then the raise lands on the next contract, not the current invoice."),
]
COMMENT_PICK = "Post the first. It concedes something real and has a year and a cost in it."

# -------------------------------------------------------------------- ig-reply
REPLY_INPUT = [
    ("@sam_builds", "TEMPLATE"),
    ("@kira.design", "TEMPLATE please!"),
    ("@jo_freelance", "template"),
    ("@mattdoesux", "We had this exact thing happen in June, client sat on approval for three weeks"),
    ("@agencyalex", "Counterpoint: kill fees scare off enterprise buyers, we lost two deals over it"),
    ("@newbie.nina", "What do you do if they refuse to sign it?"),
    ("@lena.studio", "🔥🔥🔥"),
    ("@tomwrites", "so true"),
    ("@growthguru_99", "Want 10k followers? DM me for a growth package!!"),
    ("@angryanon", "lol imagine needing a template to write a doc"),
]
REPLY_BUCKETS = {
    "KEYWORD": ["@sam_builds", "@kira.design", "@jo_freelance"],
    "LEAD": ["@mattdoesux"],
    "SUBSTANCE": ["@agencyalex"],
    "QUESTION": ["@newbie.nina"],
    "SUPPORT": ["@lena.studio", "@tomwrites"],
    "NOISE": ["@growthguru_99", "@angryanon"],
}
REPLIES = {
    "@sam_builds": "Sam, sent. Check your DMs.",
    "@kira.design": "Kira, it's in your inbox now.",
    "@jo_freelance": "Jo, just sent it over.",
    "@mattdoesux": "Matt, three weeks is brutal. What fixed it for us was moving the payment trigger off approval entirely, so silence stops costing you. Happy to send the wording if it's useful.",
    "@agencyalex": "Alex, fair, and enterprise is where I'd soften it too. We cap the kill fee at the first milestone for anyone with a procurement team, and it hasn't cost us a deal since. Two lost deals is a real cost, so I'd test that version before dropping it.",
    "@lena.studio": "Thanks Lena, appreciate you.",
    "@tomwrites": "Appreciate it, Tom.",
}
REPLY_QUESTION_TO_REEL = ("@newbie.nina", "What do you do if they refuse to sign it?", 16)

# ----------------------------------------------------------------------- ig-dm
DM_INPUT = "@sam_builds commented TEMPLATE on my proposal reel. What do I send them? Template link: https://dana.studio/template"
DM_KEYWORD = "Sam, here it is: https://dana.studio/template\n\nStart on page one. Those six questions are the ones your clients ask before they sign, and once you've answered them the rest of the proposal takes about 20 minutes.\n\nWhat are you quoting this week?"
DM_FOLLOWUPS = [
    (4, "Sam, one thing I forgot: the 30% kill fee line is on page three. That's the one people tell me they use first."),
    (10, "Last one from me, Sam. If the template helped, great. If it didn't fit how you quote, I'd love to know why, and I'll leave it there."),
]

# ---------------------------------------------------------------- ig-repurpose
REPURPOSE_SOURCE = """
Episode 41 transcript, 'Why we killed discovery calls'. Speaker: Dana.
For three years we ran a forty-five minute discovery call before every proposal. Most of them went nowhere.
Here's the number that made me stop: we did 212 discovery calls in 2024 and 31 of them turned into paid work. That's under fifteen percent.
Discovery calls are a tax you pay to look professional. I'd say most agencies should delete them.
What replaced it was a four-question form. Budget range, deadline, who signs, and what happens if you do nothing.
The way this actually works is the form filters before anyone gets on a call. If they won't fill in four fields, they weren't going to sign a contract.
The worst one: a founder took a ninety-minute call, asked for three proposals, and then hired his cousin. I'd blocked out a whole Friday for him.
My mistake was thinking a long call meant a serious buyer. It meant a lonely one.
We got six hours a week back. That's one deleted link on our website.
Proposals go out the same day now because we already have the answers.
Our close rate went from 15 percent to 38 percent in two quarters.
If they can't tell you the budget, you're not talking to the buyer.
"""
REPURPOSE_FOUND = {"claims": 2, "numbers": 8, "stories": 1, "mechanisms": 2, "mistakes": 1, "lines": 3}
REPURPOSE_WEEK = [
    ("TUE", "REEL", 2, "Stop running discovery calls before every proposal."),
    ("WED", "CAROUSEL", None, "The four-question form that replaced our discovery call"),
    ("FRI", "REEL", 21, "...and then he hired his cousin. I'd blocked out a whole Friday."),
    ("SUN", "REEL", 23, "212 discovery calls. 31 paid projects."),
    ("SUN", "STORY", None, "If they can't tell you the budget, you're not talking to the buyer."),
]

# ------------------------------------------------------------------- ig-audit
# views, reach, nonfollower_pct, hold3s_pct, shares(sends), follows, formula, format, length_s, theme
AUDIT_POSTS = [
    ("Jul 02", 74600, 70100, 62, 71, 128, 210, 3, "reel", 24, "mistake"),
    ("Jul 05", 4100, 3900, 21, 48, 9, 6, 11, "reel", 41, "tools"),
    ("Jul 09", 26300, 24800, 48, 64, 71, 88, 1, "reel", 28, "mistake"),
    ("Jul 12", 3800, 3600, 18, 44, 4, 3, None, "carousel", 0, "tools"),
    ("Jul 16", 5200, 4900, 25, 51, 12, 9, 9, "reel", 33, "templates"),
    ("Jul 19", 1200, 1150, 9, 31, 2, 1, 11, "reel", 52, "tools"),
    ("Jul 23", 18900, 17500, 55, 66, 4, 7, 22, "reel", 19, "opinion"),
    ("Jul 26", 4400, 4100, 22, 47, 18, 11, None, "carousel", 0, "templates"),
    ("Jul 30", 2900, 2800, 14, 38, 3, 2, 11, "reel", 47, "tools"),
    ("Aug 02", 11700, 10900, 41, 61, 64, 52, 15, "reel", 26, "mistake"),
    ("Aug 06", 4000, 3800, 20, 58, 90, 34, 6, "reel", 22, "templates"),
    ("Aug 09", 3600, 3400, 17, 40, 5, 2, None, "single", 0, "personal"),
]

# -------------------------------------------------------------------- ig-plan
PLAN_INPUT = {
    "sells": "A $49 proposal template, and proposal-writing retainers, to freelancers and 2-10 person agencies.",
    "themes": ["proposals", "pricing", "client contracts", "running a small agency"],
    "this_week": "Lost a $12k pitch because our deck went out two days after the competitor's. Built a same-day proposal checklist. A client paid a kill fee for the first time.",
    "accounts": ["@pricingpaul", "@agencyjen", "@proposalpro", "@freelancefin", "@designdana", "@copyclare", "@studio.mae", "@ops.olu", "@brandbybea", "@founder.finn"],
}
PLAN = [
    ("MON", None, None, None, None, "engage only"),
    ("TUE", "7:30am", "REEL", "PROOF", 1, "Lost a $12k pitch by two days"),
    ("WED", None, "STORIES", None, None, "stories + engage"),
    ("THU", "7:30am", "CAROUSEL", "TEACH", None, "The same-day proposal checklist, 7 slides"),
    ("FRI", "7:30am", "REEL", "OPINION", 22, "Fast beats good on proposals"),
    ("SAT", None, None, None, None, "-"),
    ("SUN", "8:00am", "REEL", "STORY", 21, "The day a client actually paid the kill fee"),
]
PLAN_ENGAGE = {"reach": ["@pricingpaul", "@proposalpro", "@agencyjen", "@brandbybea", "@founder.finn"],
               "peers": ["@freelancefin", "@designdana", "@studio.mae"],
               "buyers": ["@ops.olu", "@copyclare"]}

# ----------------------------------------------------------------- ig-profile
PROFILE_INPUT = {
    "name_field": "Dana Ruiz ☕",
    "handle": "@dana.proposals",
    "bio": "Designer | Founder | Coffee addict ☕ | Dog mom 🐶\nHelping people win 🚀",
    "link": "linktr.ee/danaruiz (9 links)",
    "highlights": ["Random", "Life", "2023", "Faves"],
    "pinned": [],
    "grid": "6 of 9 covers are a face mid-sentence, no text",
    "photo": "logo",
    "account": "personal",
    "last_post_days": 3,
    "story_ring": "most days",
}
PROFILE_SCORE_BEFORE = {"name_field": 2, "bio_first_line": 2, "bio_body": 2, "pinned_three": 0, "link": 2,
                        "highlights": 2, "grid_legibility": 3, "photo": 1, "handle": 5, "category_contact": 0,
                        "recent_activity": 8, "story_presence": 5}
PROFILE_REWRITES = {
    "name_field": ["Dana Ruiz | Proposal templates", "Dana | Freelance proposals", "Dana Ruiz | Agency proposals"],
    "bio": "Freelancers and small agencies: send the proposal the same day.\n212 discovery calls taught me the form below. $49.",
    "highlights": ["Pricing", "Results", "How it works", "About"],
    "link": "dana.studio/template",
}
PROFILE_SCORE_AFTER = {"name_field": 11, "bio_first_line": 10, "bio_body": 7, "pinned_three": 0, "link": 7,
                       "highlights": 7, "grid_legibility": 3, "photo": 1, "handle": 5, "category_contact": 0,
                       "recent_activity": 8, "story_presence": 5}

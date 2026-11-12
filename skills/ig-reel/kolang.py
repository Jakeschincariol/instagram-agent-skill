#!/usr/bin/env python3
"""
kolang.py - Korean support for hookscore.py and beats.py.

Why this file exists: both scripts split words with [A-Za-z0-9...], which finds
nothing in Hangul. A seven-eojeol Korean hook counted as "1 word", every check
collapsed to the same score, and beats.py timed a 23-second script at 2.2s.

What it does, in one idea: Korean is measured in syllables, then converted to
the English word count that takes the same time to say. Every band, flag and
threshold in the original scripts is calibrated against English words at 165
wpm, so converting once at the front leaves all of that logic untouched and
correct. For Latin text every function here is a no-op.

Speaking rate: 5.5 Hangul syllables per second (330/min), which is normal
on-camera short-form delivery. Slower than a news reader, faster than a lecture.
Override with --spm if you have timed yourself.
"""

import re

HANGUL = r"가-힣"
HANGUL_RE = re.compile(f"[{HANGUL}]")
EOJEOL_RE = re.compile(f"[{HANGUL}0-9%]+")

KO_SYL_PER_SEC = 5.5        # Hangul syllables per second, spoken
EN_WORDS_PER_SEC = 2.75     # 165 wpm, the rate both scripts assume


def syllables(text):
    return len(HANGUL_RE.findall(text))


def is_korean(text):
    """True when Hangul carries the line, not when it merely appears in it."""
    han = syllables(text)
    latin = len(re.findall(r"[A-Za-z]", text))
    return han > 0 and han >= latin


def eojeol(text):
    """Korean words, particles attached, the way they are spoken."""
    return EOJEOL_RE.findall(text)


def duration(text, syl_per_sec=KO_SYL_PER_SEC, en_words_per_sec=EN_WORDS_PER_SEC):
    """Seconds to say this out loud. Counts Hangul and Latin separately."""
    han = syllables(text)
    latin = len(re.findall(r"[A-Za-z0-9$%'’-]+", re.sub(r"[^\x00-\x7f]", " ", text)))
    return han / syl_per_sec + latin / en_words_per_sec


def equiv_words(text, syl_per_sec=KO_SYL_PER_SEC, en_words_per_sec=EN_WORDS_PER_SEC):
    """
    The English word count that takes the same time to say. This is the whole
    trick: hand this to logic written for English and it behaves correctly.
    """
    return duration(text, syl_per_sec, en_words_per_sec) * en_words_per_sec


def display_width(text):
    """Hangul renders about twice as wide as a Latin character on screen."""
    han = syllables(text)
    return len(text.strip()) + han


# --- markers -----------------------------------------------------------------
# Korean attaches particles to the stem, so these match as substrings rather
# than as set membership. Anything one syllable long is matched as a whole
# eojeol instead, or "안" would hit 안녕, 제안 and 불안.

STAKES_KO = (
    "실수", "잃", "손해", "실패", "망했", "망하", "그만", "버리", "버려", "틀렸",
    "틀린", "거짓", "비밀", "숨기", "숨긴", "몰랐", "아무도", "절대", "문제",
    "위험", "후회", "대신", "하지만", "오히려", "공짜", "무료", "처음", "최악",
    "손실", "낭비", "사기", "속았", "속지", "포기", "날렸", "날리", "까먹",
    "함정", "착각", "금지", "불가능", "없", "아니", "말고", "마세요", "지마",
    "끊", "짜증", "억울", "놓쳤", "놓치", "뺏", "잘못", "하나도", "전까지",
    # "않" is the main long-form negation and only ever appears in 않다/않아/
    # 않은, so it is safe as a bare substring. Without it "좋아지지 않아요"
    # reads as a line with nothing at stake.
    "않", "힘들", "불편", "걱정", "두려", "무섭", "아프", "통증", "어쩔",
)
STAKES_KO_SOLO = ("안", "못", "왜")

NUMBERS_KO = (
    "하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉", "열",
    "스물", "서른", "마흔", "쉰", "예순", "백", "천", "만", "억", "조",
    "절반", "두배", "세배", "반년",
)
# A counter on its own is not concrete, and most of them are one syllable that
# turns up inside ordinary words: "건" is in 이건, "만" is in 하지만, "조" is in
# 조금. So a counter only counts when a number is sitting in front of it.
_NUM_WORD = ("(?:하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉|열|"
             "스물|서른|마흔|쉰|예순|백|천|만|억|절반|반)")
_UNIT = ("(?:원|퍼센트|프로|배|명|개|번|분|초|시간|년|개월|달|주|일|주일|"
         "킬로|달러|회|건|점|평|표|가지|군데|층|권|잔|판|대)")
KO_COUNT_RE = re.compile(r"(?:\d[\d,.]*|" + _NUM_WORD + r") ?" + _UNIT)
# These are concrete on their own, the way "revenue" and "salary" are.
MONEY_KO = (
    "매출", "수익", "월급", "연봉", "월세", "보증금", "원가", "마진", "적자",
    "흑자", "순이익", "객단가",
)

WEAK_OPENERS_KO = (
    "안녕", "반갑", "여러분", "오늘은", "오늘", "이번에는", "이번", "그래서",
    "그러니까", "혹시", "다들", "요즘", "여기", "이거는", "자", "음", "어",
    "사실은", "일단", "아무튼", "근데",
)

IMPERATIVES_KO = (
    "하지마", "하지", "멈춰", "그만", "보세요", "저장", "따라", "써보", "해보",
    "시작", "버려", "지워", "믿지", "절대", "당장", "지금", "외워", "적어",
    "기억", "확인", "비교", "바꿔", "꺼내", "열어",
)

ADDRESS_2ND = ("당신", "여러분", "너는", "너도", "네가", "니가", "본인", "그대")
ADDRESS_IMPERATIVE = ("세요", "십시오", "봐요", "보자", "해봐", "해보", "지마", "자요")
ADDRESS_QUESTION = ("나요", "까요", "시죠", "래요", "는가", "던가", "니까")
# Korean drops the second person pronoun almost always, and encodes the
# listener in the verb ending instead. A 해요체 or 합니다체 sentence has an
# addressee by grammar, so these endings are the real equivalent of "you".
ADDRESS_POLITE = ("요", "습니다", "ㅂ니다", "입니다", "에요", "예요")
ADDRESS_CONDITIONAL = ("하면", "다면", "라면", "면서", "으면")
ADDRESS_1ST = ("저는", "제가", "저도", "나는", "내가", "우리", "저희", "제", "내")

# Two-syllable prefixes that carry no meaning for loop detection.
STOP_KO = {
    "그리", "그런", "하지", "그래", "이것", "저것", "그것", "저는", "제가",
    "나는", "내가", "우리", "당신", "여러", "아주", "정말", "진짜", "너무",
    "그냥", "하는", "하고", "해서", "이런", "어떤", "무슨", "것은", "것이",
    "있는", "있어", "없는", "그거", "이거", "저거", "때문", "지금", "다시",
}


def _has(text, markers):
    return [m for m in markers if m in text]


def stakes(text):
    """Tension markers in a Korean line."""
    hits = _has(text, STAKES_KO)
    for tok in eojeol(text):
        for solo in STAKES_KO_SOLO:
            if tok == solo and solo not in hits:
                hits.append(solo)
    return sorted(set(hits))


def numbers(text):
    """Concrete markers: digits, counted things, money."""
    hits = re.findall(r"\d[\d,.]*", text)
    hits += KO_COUNT_RE.findall(text)
    hits += [t for t in eojeol(text) if t in NUMBERS_KO]
    hits += _has(text, MONEY_KO)
    # "2년" and "2" are one marker, not two. Keep the longest form of each.
    uniq = sorted(set(hits), key=len, reverse=True)
    kept = [h for i, h in enumerate(uniq) if not any(h in o for o in uniq[:i])]
    return sorted(kept)


def weak_opener(text):
    toks = eojeol(text)
    if not toks:
        return None
    head = " ".join(toks[:2])
    for weak in WEAK_OPENERS_KO:
        if toks[0] == weak or head.startswith(weak):
            return weak
    return None


def imperative_opener(text):
    toks = eojeol(text)
    if not toks:
        return None
    for imp in IMPERATIVES_KO:
        if toks[0].startswith(imp):
            return imp
    return None


def address(text):
    """How directly the line speaks to one viewer. Mirrors the English tiers."""
    if _has(text, ADDRESS_2ND):
        return 100.0, "시청자를 직접 부름"
    imp = imperative_opener(text)
    if imp:
        return 90.0, f"명령형으로 시작 (\"{imp}\")"
    if _has(text, ADDRESS_IMPERATIVE):
        return 90.0, "청자에게 시키는 종결어미"
    if _has(text, ADDRESS_QUESTION):
        return 85.0, "청자에게 묻는 종결어미"
    if _has(text, ADDRESS_CONDITIONAL):
        return 80.0, "조건절로 청자 상황을 가정"
    tail = text.rstrip().rstrip(".!?…\"'’”")[-4:]
    if any(e in tail for e in ADDRESS_POLITE):
        return 80.0, "경어체 종결 - 듣는 사람이 전제됨"
    if any(t in ADDRESS_1ST for t in eojeol(text)):
        return 70.0, "1인칭, 청자는 호명되지 않음"
    return 35.0, "3인칭, 듣는 사람이 없음"


def payload_index(text):
    """Which eojeol the interesting word sits in. None if there isn't one."""
    toks = eojeol(text)
    marks = set(stakes(text))
    for i, tok in enumerate(toks):
        if re.search(r"\d", tok) or KO_COUNT_RE.search(tok):
            return i
        if tok in NUMBERS_KO or any(m in tok for m in MONEY_KO):
            return i
        if any(m in tok for m in marks):
            return i
    return None


def stems(text):
    """Two-syllable stems, for checking whether the last beat loops the hook."""
    out = set()
    for tok in eojeol(text):
        han = "".join(HANGUL_RE.findall(tok))
        if len(han) >= 2 and han[:2] not in STOP_KO:
            out.add(han[:2])
        for m in re.findall(r"\d[\d,.]*", tok):
            out.add(m)
    return out

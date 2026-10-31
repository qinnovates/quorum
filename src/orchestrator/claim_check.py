"""Zero-token checks that a found quote can carry the claim built on it.

Finding a quote on a page does not show it supports the claim. These checks
compare numbers, comparators, direction, negation and topic. They are
heuristics: a failed check lowers a claim's tier, passing never proves support,
and paraphrase, spelled-out numbers and look-alike letters can get past them.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

NUMBER_MISMATCH = "number_mismatch"
DIRECTION_MISMATCH = "direction_mismatch"
POLARITY_MISMATCH = "polarity_mismatch"
OFF_TOPIC = "off_topic"
MIN_SHARED_TERM_RATIO = 0.25
MIN_TERM_CHARS = 4
TERM_STEM_CHARS = 5
CONTEXT_WORDS = 8
MAX_CHECK_CHARS = 4_000
MAX_COMBINING_RUN = 30
UNIT_ALIASES = {"percent": "%", "pct": "%", "sec": "s", "seconds": "s", "second": "s"}
_UNITS = r"%|percent|pct|ms|sec|seconds|second|s|min|hours|days|kb|mb|gb|tb|k|m|bn|million|billion|x"
_NUMBER = re.compile(rf"(?<![\w.])([<>≤≥])? ?([-−]?)\$?(\d[\d,]*(?:\.\d+)?) ?({_UNITS})?(?!\w)", re.IGNORECASE)
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
_ABBREVIATION = re.compile(r"\b(e\.g|i\.e|et al|vs|fig|cf)\.", re.IGNORECASE)
_BENIGN_NOT = re.compile(r"\bnot (only|just|merely)\b")
COMPARATOR_PHRASES = (
    ("at least", "≥"), ("no less than", "≥"), ("more than", ">"), ("greater than", ">"), ("over", ">"),
    ("above", ">"), ("exceeds", ">"), ("at most", "≤"), ("no more than", "≤"), ("less than", "<"),
    ("fewer than", "<"), ("under", "<"), ("below", "<"),
)
_COMPARATOR_PHRASE = re.compile(
    r"\b(" + "|".join(phrase for phrase, _ in COMPARATOR_PHRASES) + r")(?= ?[-−$]?\d)", re.IGNORECASE
)
_COMPARATOR_SYMBOLS = dict(COMPARATOR_PHRASES)
_UPWARD = frozenset({">", "≥"})
_DIRECTION_PAIRS = (
    ({"increase", "increases", "increased", "rose", "rises", "raises", "raised"},
     {"decrease", "decreases", "decreased", "fell", "falls", "lowers", "lowered", "reduces", "reduced"}),
    ({"higher", "faster", "better", "stronger", "larger", "more"}, {"lower", "slower", "worse", "weaker", "smaller", "less"}),
    ({"safe", "secure"}, {"unsafe", "insecure"}),
)
_NEGATORS = frozenset({
    "not", "no", "never", "neither", "nor", "none", "without", "cannot", "failed", "fails", "fail",
    "unlikely", "refuted", "refutes", "disproved", "disproven", "rejected", "false", "myth", "denied",
    "debunked", "unproven", "unsupported",
})
_STOP_TERMS = frozenset({"that", "this", "with", "from", "have", "been", "were", "they", "their", "which", "than"})


@lru_cache(maxsize=None)
def _starts_as_mark(character: str) -> bool:
    """True if a character decomposes to a leading combining mark, as U+0F73 does."""
    return unicodedata.combining(unicodedata.normalize("NFKD", character)[0]) != 0


def _limit_combining_runs(text: str) -> str:
    """Normalizing long runs of marks is quadratic and blocks every thread, so runs are capped first."""
    kept, run = [], 0
    for character in text:
        run = run + 1 if _starts_as_mark(character) else 0
        if run <= MAX_COMBINING_RUN:
            kept.append(character)
    return "".join(kept)


def fold_text(text: str) -> str:
    """Remove formatting tricks: compatibility forms, invisible marks, curly quotes."""
    composed = unicodedata.normalize("NFKC", _limit_combining_runs(text))
    visible = "".join(ch for ch in composed if unicodedata.category(ch) != "Cf")
    return re.sub(r"\s+", " ", visible.replace("’", "'")).strip()


def _prepared(text: str) -> str:
    """Bounded and folded, so hostile length and spacing cannot stall the checks."""
    return fold_text(text[:MAX_CHECK_CHARS])


def _numbers(text: str) -> list[tuple[str, str, str]]:
    """(comparator, signed value, unit) for each number in the text."""
    spelled = _COMPARATOR_PHRASE.sub(lambda m: _COMPARATOR_SYMBOLS[m.group(1).lower()], text)
    found = []
    for comparator, sign, value, unit in _NUMBER.findall(spelled):
        normalized_unit = unit.lower()
        signed = f"{'-' if sign else ''}{value.replace(',', '')}"
        found.append((comparator, signed, UNIT_ALIASES.get(normalized_unit, normalized_unit)))
    return found


def _compatible(claimed: tuple[str, str, str], quoted: tuple[str, str, str]) -> bool:
    is_opposed = bool(claimed[0] and quoted[0]) and (claimed[0] in _UPWARD) != (quoted[0] in _UPWARD)
    is_same_unit = not claimed[2] or claimed[2] == quoted[2]
    return claimed[1] == quoted[1] and not is_opposed and is_same_unit


def _words(text: str) -> list[str]:
    return _WORD.findall(_BENIGN_NOT.sub(" ", text.lower()))


def _is_negated(text: str) -> bool:
    return any(word in _NEGATORS or word.endswith("n't") for word in _words(text))


def _direction_conflict(claim: str, quote: str) -> bool:
    claimed, quoted = set(_words(claim)), set(_words(quote))
    for first, second in _DIRECTION_PAIRS:
        if (claimed & first and quoted & second and not quoted & first) or (
            claimed & second and quoted & first and not quoted & second
        ):
            return True
    return False


def _words_before(context: str) -> str:
    """Words just before the quote, within its sentence."""
    sentence = _SENTENCE_END.split(_ABBREVIATION.sub(r"\1", context))[-1]
    return " ".join(sentence.split()[-CONTEXT_WORDS:])


def _words_after(context: str) -> str:
    sentence = _SENTENCE_END.split(_ABBREVIATION.sub(r"\1", context))[0]
    return " ".join(sentence.split()[:CONTEXT_WORDS])


def _terms(text: str) -> set[str]:
    return {w[:TERM_STEM_CHARS] for w in _words(text) if len(w) >= MIN_TERM_CHARS and w not in _STOP_TERMS}


def _polarity_differs(claim: str, quote: str, contexts: tuple[tuple[str, str], ...]) -> bool:
    """Any place the quote appears can contradict the claim."""
    readings = contexts or (("", ""),)
    return any(
        _is_negated(claim) != _is_negated(f"{_words_before(before)} {quote} {_words_after(after)}")
        for before, after in readings
    )


def support_issues(claim: str, quote: str, contexts: tuple[tuple[str, str], ...] = ()) -> tuple[str, ...]:
    """Why this quote may not support this claim. Empty when no check failed."""
    claim, quote = _prepared(claim), _prepared(quote)
    issues = []
    quoted_numbers = _numbers(quote)
    if not all(any(_compatible(item, other) for other in quoted_numbers) for item in _numbers(claim)):
        issues.append(NUMBER_MISMATCH)
    if _direction_conflict(claim, quote):
        issues.append(DIRECTION_MISMATCH)
    if _polarity_differs(claim, quote, tuple((_prepared(b), _prepared(a)) for b, a in contexts)):
        issues.append(POLARITY_MISMATCH)
    claim_terms = _terms(claim)
    shared = claim_terms & _terms(quote)
    if claim_terms and len(shared) / len(claim_terms) < MIN_SHARED_TERM_RATIO:
        issues.append(OFF_TOPIC)
    return tuple(issues)

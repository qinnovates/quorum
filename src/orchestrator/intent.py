"""Deterministic intent step: ask, state assumptions, or proceed."""

from __future__ import annotations

import re
from dataclasses import dataclass

ASK_THRESHOLD = 2
_SIGNALS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("scope", "What system or decision does this cover?", re.compile(r"(?i)\b(for|in|on|our|my|the)\s+\w+")),
    ("constraints", "What constraints apply, such as budget, time or risk?", re.compile(r"(?i)\b(must|budget|under|within|without|limit|deadline|cost|\$\d)")),
    ("success", "How will you judge the right answer?", re.compile(r"(?i)\b(best|optimi[sz]e|goal|so that|success|criteria|priorit|measure)")),
)
_REFERENT = re.compile(r"(?i)^\s*(fix|do|change|review|improve)\s+(it|this|that)\b")
_HIGH_STAKES = re.compile(
    r"(?i)\b(irreversible|production|delete|migrat\w*|legal|medical|patient|security|acquire|hire|fire|public release|contract)\b"
)
_LOW_STAKES = re.compile(r"(?i)\b(rename|naming|draft|prototype|experiment|reversible|internal note)\b")


@dataclass(frozen=True)
class IntentResult:
    action: str
    questions: tuple[str, ...]
    assumptions: tuple[str, ...]
    stakes: str


def classify_stakes(question: str) -> str:
    if _HIGH_STAKES.search(question):
        return "high"
    return "low" if _LOW_STAKES.search(question) else "medium"


def assess_intent(question: str) -> IntentResult:
    """Ask at two or more signals, state an assumption at one, else proceed."""
    if not question.strip():
        raise ValueError("question is empty; say what decision you need")
    prompts = [text for _, text, pattern in _SIGNALS if not pattern.search(question)]
    if _REFERENT.search(question):
        prompts.append("What does 'it' refer to?")
    if question.count("?") > 1:
        prompts.append("Which single question should this run answer first?")
    stakes = classify_stakes(question)
    if len(prompts) >= ASK_THRESHOLD:
        return IntentResult("ask", tuple(prompts[:4]), (), stakes)
    if prompts:
        return IntentResult("assume", (), (f"Unanswered: {prompts[0]}",), stakes)
    return IntentResult("proceed", (), (), stakes)

"""Relevance scoring against the user's qualifications."""
from __future__ import annotations

WEIGHTS = {"strong": 4, "medium": 3, "weak": 1}


def score(text: str, keywords: dict, boost_phrases: list[str] | None = None) -> tuple[int, list[str]]:
    """Return (score, matched phrases). Excluded phrases force a score of 0."""
    low = " " + " ".join(text.lower().split()) + " "
    for bad in keywords.get("exclude", []) or []:
        if bad.lower() in low:
            return 0, [f"excluded:{bad}"]

    total = 0
    matched: list[str] = []
    for tier, weight in WEIGHTS.items():
        for phrase in keywords.get(tier, []) or []:
            phrase_low = phrase.lower()
            # short tokens must match as whole words
            needle = f" {phrase_low} " if len(phrase_low) <= 4 else phrase_low
            if needle in low:
                total += weight
                matched.append(phrase)
    for phrase in boost_phrases or []:
        if phrase.lower() in low:
            total += 3
            matched.append(f"boost:{phrase}")
    return total, matched

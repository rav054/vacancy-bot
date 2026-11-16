"""Open a notification page and look for the real last date to apply.

News headlines almost never carry the deadline, which is exactly the thing the
reminders need. This module fetches a candidate page once and looks for a date
sitting next to a closing-date phrase.
"""
from __future__ import annotations

import datetime as dt
import re

from .util import fetch, parse_date, strip_tags

# Phrases that introduce a closing date, most specific first.
CLOSING_PHRASES = [
    r"last date (?:and time )?(?:of|for|to)?\s*(?:receipt of\s*)?(?:online\s*)?"
    r"(?:submission|application|applications|apply|registration|registering)?",
    r"last date of online application",
    r"closing date(?: of| for)?",
    r"application(?:s)? (?:close|closes|closing) (?:on|date)?",
    r"apply (?:online )?(?:on or )?before",
    r"online application(?:s)? (?:can be submitted )?(?:till|upto|up to|until)",
    r"registration (?:ends|closes|last date)",
    r"deadline(?: to apply| for application)?",
    r"on or before",
    r"till",
]

WINDOW = 120  # characters searched after the phrase


def find_deadline(text: str, *, today: dt.date | None = None,
                  max_future_days: int = 400, max_past_days: int = 5) -> dt.date | None:
    """Best guess at the closing date mentioned in a page's text."""
    today = today or dt.date.today()
    flat = " ".join(text.split())
    for phrase in CLOSING_PHRASES:
        for match in re.finditer(phrase, flat, re.IGNORECASE):
            tail = flat[match.end(): match.end() + WINDOW]
            found = parse_date(tail)
            if not found:
                continue
            delta = (found - today).days
            if -max_past_days <= delta <= max_future_days:
                return found
    return None


def enrich_item(item: dict, *, timeout: int = 25, user_agent: str = "Mozilla/5.0",
                insecure: bool = False) -> bool:
    """Try to fill in item['last_date']. Returns True if it changed."""
    if item.get("last_date") or item.get("deadline_override"):
        return False
    url = item.get("url")
    if not url or url.lower().endswith(".pdf"):
        return False
    # Google News article links are a JavaScript shell with no readable text.
    if "news.google.com" in url:
        item["enriched"] = True
        return False
    try:
        body = fetch(url, timeout=timeout, user_agent=user_agent, retries=1,
                     insecure=insecure)
    except Exception:  # noqa: BLE001 - enrichment is best effort
        item["enrich_failed"] = True
        return False
    found = find_deadline(strip_tags(body))
    item["enriched"] = True
    if found:
        item["last_date"] = found.isoformat()
        item["last_date_source"] = "page text (verify on the official notice)"
        return True
    return False

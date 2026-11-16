"""JSON-backed store that never loses the fields you edited by hand."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from .util import from_iso

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "vacancies.json"

# Fields the bot must never overwrite once you have set them.
USER_FIELDS = ("applied", "dismissed", "deadline_override", "notes", "notified",
               "checked_items")


def make_id(source_id: str, title: str, advt_no: str = "", url: str = "") -> str:
    key = re.sub(r"[^a-z0-9]+", " ", f"{title} {advt_no}".lower()).strip()
    if not key:
        key = url.lower()
    digest = hashlib.sha1(f"{source_id}|{key}".encode()).hexdigest()[:12]
    return f"{source_id}-{digest}"


_STOP = {"the", "for", "and", "out", "check", "here", "now", "with", "from", "all",
         "apply", "online", "offline", "details", "notification", "recruitment",
         "vacancy", "vacancies", "posts", "post", "notice", "released", "begins",
         "open", "link", "how", "last", "date", "dates", "eligibility", "full",
         "announced", "process", "complete", "direct", "know", "see", "steps",
         "salary", "qualification", "age", "limit", "pdf", "download", "latest",
         "update", "updates", "news", "registration", "form", "fee", "exam"}


def signature(title: str) -> set[str]:
    """Significant tokens of a headline, for near-duplicate detection."""
    cleaned = re.sub(r"(?<=\d),(?=\d)", "", title.lower())
    words = re.findall(r"[a-z0-9]+", cleaned)
    return {w for w in words if len(w) >= 3 and w not in _STOP}


def duplicate_of(data: dict, source_id: str, title: str, *, threshold: float = 0.45,
                 cross_news: bool = False) -> str | None:
    """Return the id of an existing item whose headline says the same thing.

    With cross_news, a headline is also matched against news leads from other
    sources, because one announcement surfaces in several of the feeds.
    """
    incoming = signature(title)
    if len(incoming) < 3:
        return None
    for item_id, item in data["items"].items():
        same_source = item.get("source_id") == source_id
        if not same_source and not (cross_news and item.get("via_news")):
            continue
        other = signature(item.get("title", ""))
        if not other:
            continue
        overlap = len(incoming & other) / len(incoming | other)
        if overlap >= threshold:
            return item_id
    return None


def load() -> dict:
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}
    data.setdefault("items", {})
    data.setdefault("meta", {})
    data.setdefault("source_health", {})
    return data


def save(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def effective_last_date(item: dict) -> dt.date | None:
    return from_iso(item.get("deadline_override")) or from_iso(item.get("last_date"))


def days_left(item: dict, today: dt.date | None = None) -> int | None:
    last = effective_last_date(item)
    if not last:
        return None
    return (last - (today or dt.date.today())).days


def status_of(item: dict, today: dt.date | None = None) -> str:
    if item.get("applied"):
        return "applied"
    if item.get("dismissed"):
        return "dismissed"
    left = days_left(item, today)
    if left is None:
        return "deadline-unknown"
    if left < 0:
        return "closed"
    if left <= 3:
        return "closing-now"
    if left <= 7:
        return "closing-soon"
    return "open"


def upsert(data: dict, incoming: dict) -> tuple[bool, dict]:
    """Insert or refresh an item. Returns (is_new, stored_item)."""
    items = data["items"]
    item_id = incoming["id"]
    today = dt.date.today().isoformat()
    existing = items.get(item_id)
    if existing is None:
        incoming.setdefault("applied", False)
        incoming.setdefault("dismissed", False)
        incoming.setdefault("deadline_override", None)
        incoming.setdefault("notes", "")
        incoming.setdefault("notified", [])
        incoming.setdefault("checked_items", [])
        incoming["first_seen"] = today
        incoming["last_seen"] = today
        items[item_id] = incoming
        return True, incoming
    preserved = {field: existing.get(field) for field in USER_FIELDS if field in existing}
    first_seen = existing.get("first_seen", today)
    # Keep a last date we already know if the new scrape lost it.
    if not incoming.get("last_date") and existing.get("last_date"):
        incoming["last_date"] = existing["last_date"]
    if not incoming.get("opening_date") and existing.get("opening_date"):
        incoming["opening_date"] = existing["opening_date"]
    existing.update(incoming)
    existing.update({k: v for k, v in preserved.items() if v is not None})
    existing["first_seen"] = first_seen
    existing["last_seen"] = today
    return False, existing


def prune(data: dict, archive_after_days: int, news_lead_ttl_days: int = 0) -> int:
    """Drop long-closed items, and stale undated news leads, that you never touched."""
    today = dt.date.today()
    doomed = []
    for item_id, item in data["items"].items():
        if item.get("applied") or item.get("notes"):
            continue
        last = effective_last_date(item)
        if last and (today - last).days > archive_after_days:
            doomed.append(item_id)
            continue
        # An undated news lead goes stale: the window has almost certainly passed.
        if news_lead_ttl_days and item.get("via_news") and not last:
            seen = from_iso(item.get("published")) or from_iso(item.get("first_seen"))
            if seen and (today - seen).days > news_lead_ttl_days:
                doomed.append(item_id)
    for item_id in doomed:
        del data["items"][item_id]
    return len(doomed)

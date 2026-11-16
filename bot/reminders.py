"""Turn the stored vacancies into the alerts you actually want to see."""
from __future__ import annotations

import datetime as dt

from .store import days_left, effective_last_date, status_of


def build_events(data: dict, reminder_days: list[int], today: dt.date | None = None,
                 new_ids: set[str] | None = None) -> list[dict]:
    """New-vacancy alerts plus one alert per deadline threshold crossed."""
    today = today or dt.date.today()
    new_ids = new_ids or set()
    events: list[dict] = []

    for item_id, item in data["items"].items():
        if item.get("dismissed") or item.get("applied"):
            continue
        left = days_left(item, today)
        notified = item.setdefault("notified", [])

        # No point announcing something that was already over when we found it.
        if item_id in new_ids and not (left is not None and left < 0):
            events.append({
                "kind": "new",
                "id": item_id,
                "org": item.get("org", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "apply_page": item.get("apply_page", ""),
                "days_left": left,
                "last_date": item.get("last_date"),
                "via_news": bool(item.get("via_news")),
                "urgency": "new",
            })

        if left is None or left < 0:
            continue
        # Every threshold at or above days-left has now been crossed. Mark them
        # all as sent, or the next run fires again for each wider one.
        crossed = sorted(t for t in reminder_days if left <= t)
        if not crossed or all(t in notified for t in crossed):
            continue
        notified.extend(t for t in crossed if t not in notified)
        events.append({
            "kind": "deadline",
            "id": item_id,
            "org": item.get("org", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "apply_page": item.get("apply_page", ""),
            "days_left": left,
            "last_date": effective_last_date(item).isoformat(),
            # The tightest threshold crossed is the one that describes the urgency.
            "threshold": crossed[0],
            "urgency": "critical" if left <= 3 else "warning",
        })

    order = {"critical": 0, "warning": 1, "new": 2}
    events.sort(key=lambda e: (order.get(e["urgency"], 3), e.get("days_left") or 999))
    return events


def summarise(data: dict, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    counts: dict[str, int] = {}
    for item in data["items"].values():
        counts[status_of(item, today)] = counts.get(status_of(item, today), 0) + 1
    return counts

"""Render the self-contained HTML dashboard."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .store import days_left, status_of

OUT_FILE = Path(__file__).resolve().parent.parent / "docs" / "index.html"
TEMPLATE_FILE = Path(__file__).resolve().parent / "template.html"

CATEGORY_LABELS = {
    "central": "Central government & ISRO",
    "banking": "Banking (AFO, NABARD, RRB)",
    "psu": "PSUs (fertiliser, seed, food)",
    "state": "State services & PSCs",
    "academia": "Universities & teaching",
    "research": "ICAR & research institutes",
    "fellowship": "Fellowships (JRF/SRF/RA)",
    "private": "Private & agribusiness",
    "international": "CGIAR & international",
    "other": "Other",
}

GROUPS = [
    ("closing-now", "Act now", "Three days or less"),
    ("closing-soon", "Closing this week", "Four to seven days"),
    ("open", "Open", "More than a week to go"),
    ("deadline-unknown", "Deadline not detected", "Open the notice and set the date yourself"),
    ("applied", "Applied", "You marked these done"),
    ("closed", "Closed", "Kept for reference"),
]


def build(data: dict, checklists: dict, events: list[dict], config: dict) -> str:
    today = dt.date.today()
    items = []
    for item_id, item in data["items"].items():
        if item.get("dismissed"):
            continue
        payload = dict(item)
        payload["id"] = item_id
        payload["status"] = status_of(item, today)
        payload["days_left"] = days_left(item, today)
        family = checklists.get("families", {}).get(item.get("checklist", ""), {})
        payload["checklist_title"] = family.get("title", "General")
        payload["checklist_items"] = family.get("items", [])
        payload.pop("context", None)
        payload.pop("matched", None)
        items.append(payload)

    order = {key: index for index, (key, _, _) in enumerate(GROUPS)}
    items.sort(key=lambda e: (order.get(e["status"], 9),
                              9999 if e["days_left"] is None else e["days_left"]))

    blob = {
        "generated": dt.datetime.now().strftime("%d %b %Y, %H:%M"),
        "generated_iso": dt.datetime.now().isoformat(timespec="seconds"),
        "items": items,
        "events": events,
        "common": checklists.get("common", {}),
        "groups": [{"key": k, "label": l, "hint": h} for k, l, h in GROUPS],
        "sources": [
            {"id": s["id"], "org": s["org"], "category": s.get("category", "other"),
             "apply_page": s.get("apply_page", ""),
             "health": data.get("source_health", {}).get(s["id"], {})}
            for s in config.get("sources", [])
        ],
        "categories": CATEGORY_LABELS,
        "profile": config.get("profile", {}),
    }

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    return template.replace("/*DATA*/", json.dumps(blob, ensure_ascii=False))


def write(data: dict, checklists: dict, events: list[dict], config: dict) -> Path:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(build(data, checklists, events, config), encoding="utf-8")
    return OUT_FILE

"""Command line entry point: python -m bot <command>"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

from . import dashboard, enrich, parsers, store
from .match import score
from .reminders import build_events, summarise
from .store import days_left, status_of
from .util import fetch

ROOT = Path(__file__).resolve().parent.parent
EVENTS_FILE = ROOT / "data" / "events.json"


def load_config() -> tuple[dict, dict]:
    config = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    checklists = yaml.safe_load((ROOT / "checklists.yaml").read_text(encoding="utf-8"))
    return config, checklists


def news_ok(title: str, news_filter: dict, today: dt.date | None = None) -> bool:
    """News headlines must look like a vacancy announcement, not a press release."""
    low = " " + " ".join(title.lower().split()) + " "
    for bad in news_filter.get("exclude", []) or []:
        if str(bad).lower() in low:
            return False
    # A headline that names only past years is reporting an old cycle.
    today = today or dt.date.today()
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", title)]
    if years and max(years) < today.year:
        return False
    required = news_filter.get("require", []) or []
    if not required:
        return True
    return any(str(good).lower() in low for good in required)


def cmd_check(args: argparse.Namespace) -> int:
    config, checklists = load_config()
    settings = config.get("settings", {})
    keywords = config.get("keywords", {})
    news_filter = config.get("news_filter", {})
    news_cap = int(settings.get("news_items_per_source", 10))
    threshold = int(settings.get("relevance_threshold", 3))
    data = store.load()
    new_ids: set[str] = set()
    health: dict[str, dict] = {}

    for source in config.get("sources", []):
        sid = source["id"]
        url = source["url"]
        if source.get("parser") == "news_rss":
            url = parsers.with_news_window(url, str(settings.get("news_window", "")))
        try:
            body = fetch(
                url,
                timeout=int(settings.get("http_timeout", 30)),
                user_agent=settings.get("user_agent", "Mozilla/5.0"),
                insecure=bool(source.get("insecure")),
            )
            raw = parsers.run_parser(body, source)
        except Exception as exc:  # noqa: BLE001 - recorded, run continues
            health[sid] = {"ok": False, "error": str(exc)[:200],
                           "expected": bool(source.get("geo_restricted")),
                           "at": dt.datetime.now().isoformat(timespec="seconds")}
            tag = "skip" if source.get("geo_restricted") else "fail"
            print(f"  [{tag}] {sid}: {str(exc)[:110]}", file=sys.stderr)
            continue

        max_items = int(source.get("max_items", 0))
        if max_items:
            raw = raw[:max_items]

        anchors = [str(a).lower() for a in source.get("require_in_title", []) or []]

        kept = 0
        for entry in raw:
            if entry.get("via_news"):
                if not news_ok(entry["title"], news_filter):
                    continue
                # Google News ranking leaks unrelated orgs into narrow feeds.
                if anchors and not any(a in entry["title"].lower() for a in anchors):
                    continue
                published = entry.get("published")
                ttl = int(settings.get("news_lead_ttl_days", 0))
                if ttl and published:
                    age = (dt.date.today() - dt.date.fromisoformat(published)).days
                    if age > ttl:
                        continue
                if kept >= news_cap:
                    break
                twin = store.duplicate_of(data, sid, entry["title"], cross_news=True)
                if twin and twin != store.make_id(sid, entry["title"],
                                                  entry.get("advt_no", ""), entry["url"]):
                    continue  # same story, different outlet
            relevance, matched = score(
                f"{entry['title']} {entry.get('context', '')}",
                keywords,
                source.get("boost_phrases"),
            )
            if relevance < threshold:
                continue
            # Don't ingest what prune() would drop again on the same run; it made
            # every run report a misleading "N new, N archived".
            archive_after = int(settings.get("archive_after_days", 30))
            if entry.get("last_date"):
                closed_for = (dt.date.today() - dt.date.fromisoformat(entry["last_date"])).days
                if closed_for > archive_after:
                    continue

            item_id = store.make_id(sid, entry["title"], entry.get("advt_no", ""), entry["url"])
            payload = dict(entry)
            payload.update({
                "id": item_id,
                "source_id": sid,
                "org": source["org"],
                "category": source.get("category", "other"),
                "apply_page": source.get("apply_page", ""),
                "checklist": source.get("checklist", ""),
                "score": relevance,
                "matched": matched[:8],
            })
            is_new, _ = store.upsert(data, payload)
            if is_new:
                new_ids.add(item_id)
            kept += 1

        health[sid] = {"ok": True, "scanned": len(raw), "found": kept,
                       "at": dt.datetime.now().isoformat(timespec="seconds")}
        print(f"  [ok]   {sid}: {kept} relevant of {len(raw)} scanned")

    # Try to discover the real last date for items that arrived without one.
    if not args.no_enrich:
        budget = int(settings.get("enrich_budget", 20))
        filled = 0
        attempted = 0
        for item_id, item in data["items"].items():
            if attempted >= budget:
                break
            if item.get("last_date") or item.get("deadline_override"):
                continue
            if item.get("enriched") or item.get("dismissed") or item.get("applied"):
                continue
            attempted += 1
            if enrich.enrich_item(
                item,
                timeout=int(settings.get("http_timeout", 30)),
                user_agent=settings.get("user_agent", "Mozilla/5.0"),
            ):
                filled += 1
        if attempted:
            print(f"  [enrich] found a last date for {filled} of {attempted} undated items")

    data["source_health"] = health
    removed = store.prune(data, int(settings.get("archive_after_days", 30)),
                          int(settings.get("news_lead_ttl_days", 0)))
    events = build_events(data, settings.get("reminder_days", [14, 7, 3, 1, 0]), new_ids=new_ids)
    data["meta"] = {
        "last_run": dt.datetime.now().isoformat(timespec="seconds"),
        "new_count": len(new_ids),
        "event_count": len(events),
    }
    store.save(data)
    EVENTS_FILE.write_text(json.dumps({
        "generated": data["meta"]["last_run"], "events": events,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    out = dashboard.write(data, checklists, events, config)

    print(f"\n{len(new_ids)} new, {len(events)} alert(s), {removed} archived")
    print("status:", ", ".join(f"{k}={v}" for k, v in sorted(summarise(data).items())))
    print("dashboard:", out)
    for event in events:
        left = event.get("days_left")
        when = "date unknown" if left is None else f"{left}d left"
        print(f"  ! [{event['kind']}/{when}] {event['org']}: {event['title'][:80]}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    config, checklists = load_config()
    data = store.load()
    events = []
    if EVENTS_FILE.exists():
        events = json.loads(EVENTS_FILE.read_text(encoding="utf-8")).get("events", [])
    print("dashboard:", dashboard.write(data, checklists, events, config))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = store.load()
    today = dt.date.today()
    rows = sorted(
        data["items"].items(),
        key=lambda kv: (9999 if days_left(kv[1], today) is None else days_left(kv[1], today)),
    )
    if not rows:
        print("nothing tracked yet - run: python -m bot check")
        return 0
    for item_id, item in rows:
        state = status_of(item, today)
        if args.open_only and state in ("closed", "dismissed"):
            continue
        left = days_left(item, today)
        left_text = "  ?  " if left is None else f"{left:>4}d"
        print(f"{item_id:<22} {left_text}  {state:<16} {item['org'][:28]:<28} {item['title'][:70]}")
    return 0


def _edit(item_id: str, **changes) -> int:
    data = store.load()
    item = data["items"].get(item_id)
    if not item:
        matches = [k for k in data["items"] if k.startswith(item_id)]
        if len(matches) != 1:
            print(f"no single item matches {item_id!r}", file=sys.stderr)
            return 1
        item_id, item = matches[0], data["items"][matches[0]]
    item.update(changes)
    store.save(data)
    print(f"{item_id}: " + ", ".join(f"{k}={v}" for k, v in changes.items()))
    return 0


def cmd_applied(args: argparse.Namespace) -> int:
    return _edit(args.id, applied=True)


def cmd_dismiss(args: argparse.Namespace) -> int:
    return _edit(args.id, dismissed=True)


def cmd_deadline(args: argparse.Namespace) -> int:
    try:
        dt.date.fromisoformat(args.date)
    except ValueError:
        print("date must be YYYY-MM-DD", file=sys.stderr)
        return 1
    return _edit(args.id, deadline_override=args.date, notified=[])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bot",
                                     description="Agriculture / soil science vacancy tracker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="fetch every source, update data, rebuild dashboard")
    p_check.add_argument("--no-enrich", action="store_true",
                         help="skip opening undated notices to look for the last date")
    p_check.set_defaults(func=cmd_check)
    sub.add_parser("dashboard", help="rebuild the HTML from stored data").set_defaults(func=cmd_dashboard)

    p_list = sub.add_parser("list", help="print tracked vacancies")
    p_list.add_argument("--open-only", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_applied = sub.add_parser("applied", help="mark a vacancy as applied")
    p_applied.add_argument("id")
    p_applied.set_defaults(func=cmd_applied)

    p_dismiss = sub.add_parser("dismiss", help="hide a vacancy for good")
    p_dismiss.add_argument("id")
    p_dismiss.set_defaults(func=cmd_dismiss)

    p_deadline = sub.add_parser("deadline", help="set the real last date yourself")
    p_deadline.add_argument("id")
    p_deadline.add_argument("date", help="YYYY-MM-DD")
    p_deadline.set_defaults(func=cmd_deadline)

    args = parser.parse_args(argv)
    return args.func(args)

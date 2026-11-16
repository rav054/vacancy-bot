"""Per-source extraction. Each parser returns a list of raw item dicts."""
from __future__ import annotations

import re

from .util import absolutise, all_dates, clean_title, iso, parse_date, strip_tags

ANCHOR_RE = re.compile(r"""(?is)<a[^>]+href=(["'])(.*?)\1[^>]*>(.*?)</a>""")
ROW_RE = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
CELL_RE = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")
ITEM_RE = re.compile(r"(?is)<item>(.*?)</item>")


def _tag(fragment: str, name: str) -> str:
    match = re.search(rf"(?is)<{name}[^>]*>(.*?)</{name}>", fragment)
    return strip_tags(match.group(1)) if match else ""


def parse_isro_table(html_text: str, source: dict) -> list[dict]:
    """ISRO 'Current Opportunities' table: location | post | advt | open | last."""
    items: list[dict] = []
    for row in ROW_RE.findall(html_text):
        cells = [strip_tags(c) for c in CELL_RE.findall(row)]
        cells = [c for c in cells if c]
        if len(cells) < 4:
            continue
        joined = " ".join(cells).lower()
        if "last date" in joined and "advertisement number" in joined:
            continue  # header row
        dates = [d for cell in cells for d in all_dates(cell)]
        if not dates:
            continue
        # The post description is the longest cell that is not a bare date.
        candidates = [c for c in cells if not parse_date(c) or len(c) > 40]
        if not candidates:
            continue
        title = max(candidates, key=len)
        # A real opportunity row names a post; a stray centre name does not.
        if len(title) < 25 or not re.search(
                r"(?i)\b(recruit|post|position|appoint|engage|vacan|fellow|trainee|apprentice)", title):
            continue
        location = cells[0] if cells[0] != title else ""
        advt = ""
        for cell in cells:
            if re.search(r"(?i)\b(advt|adv|rmt|no\.?)\b|\d+[:/]\d{4}", cell) and len(cell) < 60 \
                    and cell not in (title, location):
                advt = cell
                break
        link = ""
        anchor = ANCHOR_RE.search(row)
        if anchor:
            link = absolutise(source["url"], anchor.group(2))
        items.append({
            "title": clean_title(title),
            "url": link or source["url"],
            "advt_no": advt,
            "location": location,
            "opening_date": iso(dates[0]) if len(dates) > 1 else None,
            "last_date": iso(dates[-1]) if dates else None,
            "context": " | ".join(cells)[:400],
        })
    return items


def parse_anchors(html_text: str, source: dict) -> list[dict]:
    """Every reasonably-long link on a notice board."""
    must = [m.lower() for m in source.get("link_must_match", [])]
    items: list[dict] = []
    seen: set[str] = set()
    for _, href, inner in ANCHOR_RE.findall(html_text):
        text = clean_title(strip_tags(inner))
        if len(text) < 20:
            continue
        low = text.lower()
        if must and not any(m in low for m in must):
            continue
        # Navigation blocks and menu dumps masquerade as long links.
        if "-->" in text:
            continue
        words = text.split()
        if len(words) < 4:
            continue
        counts: dict[str, int] = {}
        for word in (w.lower().strip(".,:;()-") for w in words):
            if len(word) >= 4:  # ignore "of", "the", "for"
                counts[word] = counts.get(word, 0) + 1
        if counts and max(counts.values()) >= 3:
            continue
        if not re.search(r"\d", text) and not re.search(
                r"(?i)\b(notification|advertisement|advt|vacanc|recruitment|applications? (are )?invited)", text):
            continue
        key = low[:90]
        if key in seen:
            continue
        seen.add(key)
        dates = all_dates(text)
        advt = ""
        match = re.search(r"(?i)(advt\.?\s*no\.?\s*[\w./\-]+|no\.?\s*\d+[/-]\d{4})", text)
        if match:
            advt = match.group(1)
        items.append({
            "title": text,
            "url": absolutise(source["url"], href),
            "advt_no": advt,
            "location": "",
            "opening_date": None,
            "last_date": iso(dates[-1]) if dates else None,
            "context": text,
        })
    return items


def parse_news_rss(xml_text: str, source: dict) -> list[dict]:
    """Google News RSS safety net for JavaScript-only sites."""
    items: list[dict] = []
    for block in ITEM_RE.findall(xml_text):
        title = _tag(block, "title")
        if not title:
            continue
        # Google News appends " - Publisher"
        publisher = _tag(block, "source")
        if publisher and title.endswith(f"- {publisher}"):
            title = title[: -len(publisher) - 2]
        link = _tag(block, "link") or source["url"]
        pub = parse_date(_tag(block, "pubDate"))
        dates = all_dates(title)
        items.append({
            "title": clean_title(title),
            "url": link,
            "advt_no": "",
            "location": "",
            "opening_date": None,
            "last_date": iso(dates[-1]) if dates else None,
            "published": iso(pub),
            "via_news": True,
            "context": f"{title} ({publisher})" if publisher else title,
        })
    return items


def with_news_window(url: str, window: str) -> str:
    """Append Google News's `when:` operator to the q= parameter.

    Without it the feed is ranked by relevance and is dominated by years-old
    stories; with it, nearly every item is recent.
    """
    if not window or "news.google.com" not in url or "when:" in url:
        return url
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    parts = urlparse(url)
    params = parse_qsl(parts.query, keep_blank_values=True)
    out = []
    for key, value in params:
        if key == "q":
            value = f"{value} when:{window}"
        out.append((key, value))
    return urlunparse(parts._replace(query=urlencode(out)))


PARSERS = {
    "isro_table": parse_isro_table,
    "anchors": parse_anchors,
    "news_rss": parse_news_rss,
}


def run_parser(body: str, source: dict) -> list[dict]:
    parser = PARSERS.get(source.get("parser", "anchors"))
    if parser is None:
        raise ValueError(f"unknown parser {source.get('parser')!r} for {source['id']}")
    return parser(body, source)

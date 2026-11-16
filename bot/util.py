"""HTTP fetching, HTML-to-text helpers and date parsing."""
from __future__ import annotations

import datetime as dt
import html
import re
import time
import unicodedata

import requests

TODAY = dt.date.today


def fetch(url: str, *, timeout: int = 30, user_agent: str = "Mozilla/5.0",
          retries: int = 3, insecure: bool = False) -> str:
    """GET a URL and return the decoded body. Raises on final failure.

    Some Indian government sites serve an incomplete TLS chain. Set
    ``insecure: true`` on that source in sources.yaml to read it anyway; we only
    ever read public notice boards, and never send anything.
    """
    if insecure:
        try:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:  # noqa: BLE001 - warning suppression is optional
            pass
    last = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                verify=not insecure,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-IN,en;q=0.9",
                },
            )
            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as exc:  # noqa: BLE001 - surfaced by caller
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last}")


def strip_tags(fragment: str) -> str:
    """Turn an HTML fragment into collapsed plain text."""
    fragment = re.sub(r"(?is)<(script|style).*?</\1>", " ", fragment)
    text = re.sub(r"(?s)<[^>]+>", " ", fragment)
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    return " ".join(text.split())


def clean_title(title: str, limit: int = 220) -> str:
    title = " ".join(title.replace("|", " ").split())
    title = title.strip(" -–—:·.")
    return title[:limit]


def absolutise(base: str, href: str) -> str:
    if not href:
        return base
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return "https:" + href
    root = re.match(r"(https?://[^/]+)", base)
    if not root:
        return href
    if href.startswith("/"):
        return root.group(1) + href
    prefix = base.rsplit("/", 1)[0] if "/" in base.split("://", 1)[1] else base
    return prefix.rstrip("/") + "/" + href.lstrip("./")


# --------------------------------------------------------------------------
# Date parsing
# --------------------------------------------------------------------------
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_PATTERNS = [
    # 26 October 2026 / 26 Oct, 2026
    re.compile(r"\b(\d{1,2})[\s.\-]+([A-Za-z]{3,9})[\s.,\-]+(\d{4})\b"),
    # October 26, 2026
    re.compile(r"\b([A-Za-z]{3,9})[\s.\-]+(\d{1,2})(?:st|nd|rd|th)?[\s.,\-]+(\d{4})\b"),
    # 26.10.2026 / 26-10-2026 / 26/10/2026
    re.compile(r"\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b"),
    # 2026-10-26
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),
]


def parse_date(text: str) -> dt.date | None:
    """Pull the first plausible date out of a string."""
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text)
    for index, pattern in enumerate(_PATTERNS):
        match = pattern.search(text)
        if not match:
            continue
        a, b, c = match.groups()
        try:
            if index == 0:
                month = _MONTHS.get(b[:4].lower()) or _MONTHS.get(b[:3].lower())
                if not month:
                    continue
                return dt.date(int(c), month, int(a))
            if index == 1:
                month = _MONTHS.get(a[:4].lower()) or _MONTHS.get(a[:3].lower())
                if not month:
                    continue
                return dt.date(int(c), month, int(b))
            if index == 2:
                return dt.date(int(c), int(b), int(a))
            return dt.date(int(a), int(b), int(c))
        except ValueError:
            continue
    return None


def all_dates(text: str) -> list[dt.date]:
    """Every date in a string, in order of appearance, de-duplicated."""
    found: list[dt.date] = []
    for chunk in re.split(r"(?<=\d{4})\s*(?:to|-|–|—|\|)\s*", text):
        date = parse_date(chunk)
        if date and date not in found:
            found.append(date)
    if not found:
        date = parse_date(text)
        if date:
            found.append(date)
    return found


def iso(date: dt.date | None) -> str | None:
    return date.isoformat() if date else None


def from_iso(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None

"""Загрузка RSS-лент и отбор свежих новостей."""

from __future__ import annotations

import calendar
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; crypto-digest-bot/1.0)"


@dataclass(frozen=True)
class Feed:
    name: str
    url: str


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    link: str
    published: datetime


def load_feeds(path: Path) -> list[Feed]:
    """Читает feeds.txt: строки вида `URL` или `Название | URL`."""
    feeds = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name, url = (part.strip() for part in line.split("|", 1))
        else:
            name, url = "", line
        feeds.append(Feed(name=name, url=url))
    return feeds


def parse_feed(feed: Feed, content: bytes | str) -> list[NewsItem]:
    parsed = feedparser.parse(content)
    source = feed.name or parsed.feed.get("title") or feed.url
    items = []
    for entry in parsed.entries:
        title = _clean(entry.get("title", ""))
        link = entry.get("link", "")
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if not title or not link or not stamp:
            continue
        published = datetime.fromtimestamp(calendar.timegm(stamp), tz=timezone.utc)
        items.append(NewsItem(source, title, link, published))
    return items


def fetch_feed(feed: Feed, timeout: float = 20) -> list[NewsItem]:
    response = requests.get(feed.url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return parse_feed(feed, response.content)


def fetch_all(feeds: list[Feed]) -> tuple[list[NewsItem], list[Feed]]:
    """Возвращает (новости, ленты, которые не удалось загрузить)."""
    items, failed = [], []
    for feed in feeds:
        try:
            got = fetch_feed(feed)
            log.info("%s: %d записей", feed.url, len(got))
            items.extend(got)
        except Exception as exc:  # одна сломанная лента не должна ронять весь дайджест
            log.warning("Не удалось загрузить %s: %s", feed.url, exc)
            failed.append(feed)
    return items, failed


def select_fresh(
    items: list[NewsItem],
    now: datetime,
    lookback_hours: float,
    per_source: int,
) -> list[NewsItem]:
    """Оставляет новости за последние `lookback_hours`, без дублей, не больше `per_source` на источник."""
    since = now - timedelta(hours=lookback_hours)
    fresh = sorted(
        (item for item in items if since <= item.published <= now + timedelta(minutes=5)),
        key=lambda item: item.published,
        reverse=True,
    )
    seen: set[str] = set()
    counts: dict[str, int] = {}
    result = []
    for item in fresh:
        key = _normalize(item.title)
        if key in seen or item.link in seen:
            continue
        if counts.get(item.source, 0) >= per_source:
            continue
        seen.update((key, item.link))
        counts[item.source] = counts.get(item.source, 0) + 1
        result.append(item)
    return result


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize(title: str) -> str:
    return re.sub(r"[^\w]+", " ", title.lower()).strip()

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bot.digest import format_digest
from bot.feeds import Feed, NewsItem, load_feeds, parse_feed, select_fresh
from bot.telegram import split_message

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 29, 6, 0, tzinfo=timezone.utc)


def item(title, link, hours_ago, source="A"):
    published = datetime.fromtimestamp(NOW.timestamp() - hours_ago * 3600, tz=timezone.utc)
    return NewsItem(source, title, link, published)


def test_load_feeds(tmp_path):
    path = tmp_path / "feeds.txt"
    path.write_text("# comment\n\nForkLog | https://forklog.com/feed\nhttps://x.com/rss\n", encoding="utf-8")
    assert load_feeds(path) == [
        Feed("ForkLog", "https://forklog.com/feed"),
        Feed("", "https://x.com/rss"),
    ]


def test_parse_feed_skips_entries_without_date_and_strips_html():
    items = parse_feed(Feed("", "https://example.com/rss"), (FIXTURES / "sample.xml").read_bytes())
    assert [i.title for i in items] == [
        "Биткоин обновил максимум & вырос на 5%",
        "Ethereum обновление вышло",
        "Старая новость",
    ]
    assert items[0].source == "Sample Crypto News"
    assert items[0].published == datetime(2026, 9, 29, 4, 0, tzinfo=timezone.utc)


def test_select_fresh_filters_old_and_duplicates_and_limits():
    items = [
        item("Old", "https://e/old", hours_ago=30),
        item("BTC up!", "https://e/1", hours_ago=1),
        item("btc up", "https://e/2", hours_ago=2),  # дубль по заголовку
        item("Other", "https://e/1", hours_ago=3, source="B"),  # дубль по ссылке
        item("Third", "https://e/3", hours_ago=4),
        item("Fourth", "https://e/4", hours_ago=5),
    ]
    fresh = select_fresh(items, now=NOW, lookback_hours=24, per_source=2)
    assert [i.title for i in fresh] == ["BTC up!", "Third"]


def test_format_digest_escapes_html_and_groups_by_source():
    items = [item("A <b> & B", "https://e/?a=1&b=2", hours_ago=1, source="Src")]
    text = format_digest(items, NOW.astimezone(ZoneInfo("Europe/Moscow")), failed_sources=["Broken"])
    assert "29 сентября 2026" in text
    assert "<b>Src</b>" in text
    assert '• 08:00 <a href="https://e/?a=1&amp;b=2">A &lt;b&gt; &amp; B</a>' in text
    assert "Не загрузились: Broken" in text


def test_format_digest_empty():
    text = format_digest([], NOW.astimezone(ZoneInfo("Europe/Moscow")))
    assert "свежих новостей не нашлось" in text


def test_split_message_respects_limit():
    text = "\n".join(f"line {n}" for n in range(100))
    chunks = split_message(text, limit=50)
    assert all(len(c) <= 50 for c in chunks)
    assert "\n".join(chunks) == text
    assert split_message("x" * 120, limit=50) == ["x" * 50, "x" * 50, "x" * 20]

"""Сборка текста дайджеста."""

from __future__ import annotations

from datetime import datetime
from html import escape

from bot.feeds import NewsItem

MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def format_digest(items: list[NewsItem], local_now: datetime, failed_sources: list[str] = ()) -> str:
    header = f"📰 <b>Крипто-дайджест · {local_now.day} {MONTHS[local_now.month - 1]} {local_now.year}</b>"
    lines = [header]

    if not items:
        lines += ["", "За последние сутки свежих новостей не нашлось."]

    by_source: dict[str, list[NewsItem]] = {}
    for item in items:
        by_source.setdefault(item.source, []).append(item)

    for source, source_items in by_source.items():
        lines += ["", f"<b>{escape(source)}</b>"]
        for item in source_items:
            time = item.published.astimezone(local_now.tzinfo).strftime("%H:%M")
            lines.append(f'• {time} <a href="{escape(item.link, quote=True)}">{escape(item.title)}</a>')

    if failed_sources:
        lines += ["", f"⚠️ Не загрузились: {escape(', '.join(failed_sources))}"]

    return "\n".join(lines)

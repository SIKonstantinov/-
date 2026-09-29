"""Точка входа.

    python -m bot             # собрать дайджест и отправить в Telegram
    python -m bot --dry-run   # только напечатать дайджест, ничего не отправлять
    python -m bot --chat-id   # показать chat_id из последних сообщений боту
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bot import telegram
from bot.digest import format_digest
from bot.feeds import fetch_all, load_feeds, select_fresh

ROOT = Path(__file__).resolve().parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, "").strip() or default
    if value is None:
        sys.exit(f"Не задана переменная окружения {name}")
    return value


def show_chat_ids() -> None:
    updates = telegram.get_updates(env("TELEGRAM_BOT_TOKEN"))
    chats = {}
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat")
        if chat:
            chats[chat["id"]] = chat.get("username") or chat.get("title") or chat.get("first_name", "")
    if not chats:
        print("Сообщений не найдено. Напиши боту любое сообщение в Telegram и запусти снова.")
    for chat_id, name in chats.items():
        print(f"chat_id={chat_id}  ({name})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ежедневный крипто-дайджест в Telegram")
    parser.add_argument("--dry-run", action="store_true", help="напечатать дайджест вместо отправки")
    parser.add_argument("--chat-id", action="store_true", help="показать chat_id из сообщений боту")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.chat_id:
        show_chat_ids()
        return

    feeds = load_feeds(Path(env("FEEDS_FILE", str(ROOT / "feeds.txt"))))
    items, failed = fetch_all(feeds)
    if feeds and len(failed) == len(feeds):
        sys.exit("Не удалось загрузить ни одной ленты")

    now = datetime.now(timezone.utc)
    fresh = select_fresh(
        items,
        now=now,
        lookback_hours=float(env("LOOKBACK_HOURS", "24")),
        per_source=int(env("MAX_PER_SOURCE", "5")),
    )
    text = format_digest(
        fresh,
        local_now=now.astimezone(ZoneInfo(env("TIMEZONE", "Europe/Moscow"))),
        failed_sources=[feed.name or feed.url for feed in failed],
    )

    if args.dry_run:
        print(text)
        return

    telegram.send_message(env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID"), text)
    logging.info("Дайджест отправлен: %d новостей", len(fresh))


if __name__ == "__main__":
    main()

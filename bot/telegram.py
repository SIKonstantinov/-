"""Отправка сообщений через Telegram Bot API."""

from __future__ import annotations

import requests

API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LEN = 4096


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Режет текст на части по границам строк, чтобы не превысить лимит Telegram."""
    chunks, current = [], ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        # Строка длиннее лимита сама по себе — режем её жёстко.
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        current = line
    if current:
        chunks.append(current)
    return chunks


def send_message(token: str, chat_id: str, text: str) -> None:
    for chunk in split_message(text):
        response = requests.post(
            API.format(token=token, method="sendMessage"),
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": True},
            },
            timeout=30,
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram вернул ошибку: {data.get('description', response.text)}")


def get_updates(token: str) -> list[dict]:
    response = requests.get(API.format(token=token, method="getUpdates"), timeout=30)
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram вернул ошибку: {data.get('description', response.text)}")
    return data["result"]

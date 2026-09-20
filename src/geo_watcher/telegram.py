import logging
from html import escape
from typing import Protocol

import httpx

from geo_watcher.analysis import NodeReport

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4000


class Notifier(Protocol):
    async def notify(self, result: NodeReport) -> None: ...


class NullNotifier:
    async def notify(self, result: NodeReport) -> None:
        pass


class TelegramNotifier:
    def __init__(
        self,
        client: httpx.AsyncClient,
        bot_token: str,
        chat_id: int | str,
        message_thread_id: int | None = None,
    ) -> None:
        self._client = client
        self._url = API_URL.format(token=bot_token)
        self._chat_id = chat_id
        self._message_thread_id = message_thread_id

    async def notify(self, result: NodeReport) -> None:
        payload: dict[str, object] = {
            "chat_id": self._chat_id,
            "text": format_message(result),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if self._message_thread_id is not None:
            payload["message_thread_id"] = self._message_thread_id

        response = await self._client.post(self._url, json=payload)
        if response.is_error:
            logger.error(
                "Telegram returned %d: %s",
                response.status_code,
                response.text,
            )


def format_message(result: NodeReport) -> str:
    lines = [f"🌍 <b>{escape(result.node_name)}</b>: изменились проверки", ""]
    lines += [
        f"• {escape(c.observation.label)}: {escape(c.previous)} → "
        f"<b>{escape(c.current)}</b>"
        for c in result.changes
    ]

    text = "\n".join(lines)
    if len(text) > MAX_MESSAGE_LENGTH:
        cut = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        text = text[:cut] + "\n…"
    return text

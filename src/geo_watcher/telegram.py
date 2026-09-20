import logging
import time
from html import escape
from typing import Protocol

import httpx

from geo_watcher import emoji
from geo_watcher.analysis import Change, NodeReport
from geo_watcher.report import CheckKind, Observation

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendRichMessage"

MAX_LENGTH = 32000
SNAPSHOT_LIMIT = 60

# чем больше, тем хуже: так отличаем поломку от восстановления
RANKS = {
    "available": 0,
    "yes": 0,
    "restricted": 1,
    "unknown": 1,
    "no": 2,
    "blocked": 2,
}
STATE_ICONS = {0: emoji.GOOD, 1: emoji.WARN, 2: emoji.BAD}


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
        *,
        custom_emoji: bool = True,
    ) -> None:
        self._client = client
        self._url = API_URL.format(token=bot_token)
        self._chat_id = chat_id
        self._message_thread_id = message_thread_id
        self._custom_emoji = custom_emoji

    async def notify(self, result: NodeReport) -> None:
        payload: dict[str, object] = {
            "chat_id": self._chat_id,
            "rich_message": {
                "html": format_html(result, custom_emoji=self._custom_emoji),
                "skip_entity_detection": True,
            },
            "disable_notification": not _has_degradation(result.changes),
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


def _rank(kind: CheckKind, value: str) -> int:
    if kind is CheckKind.COUNTRY:
        return 0
    # blocked-проверки отвечают наоборот: "yes" значит поймали капчу
    if kind is CheckKind.BLOCKED:
        return 2 if value.startswith("yes") else 0
    return RANKS.get(value.split(" ", maxsplit=1)[0], 1)


def _severity(change: Change) -> int:
    kind = change.observation.kind
    return _rank(kind, change.current) - _rank(kind, change.previous)


def _has_degradation(changes: list[Change]) -> bool:
    return any(_severity(change) > 0 for change in changes)


def _flag(code: str) -> str:
    letters = 2
    if len(code) != letters or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(letter) - ord("A")) for letter in code)


def _value(observation: Observation, value: str, *, custom: bool) -> str:
    if observation.kind is CheckKind.COUNTRY:
        flag = _flag(value)
        return f"{flag} {escape(value)}" if flag else escape(value)
    icon = STATE_ICONS[_rank(observation.kind, value)].html(custom=custom)
    return f"{icon} {escape(value)}"


def _name(observation: Observation, *, custom: bool) -> str:
    name = escape(observation.name)
    logo = emoji.SERVICES.get(observation.id)
    if logo is not None:
        name = f"{logo.html(custom=custom)} {name}"
    if observation.family is None:
        return name
    return f"{name} <sup>{observation.family.value}</sup>"


def _icon(changes: list[Change], *, custom: bool) -> str:
    if any(_severity(change) > 0 for change in changes):
        return emoji.BAD.html(custom=custom)
    if any(_severity(change) < 0 for change in changes):
        return emoji.GOOD.html(custom=custom)
    return emoji.GEO.html(custom=custom)


def _rows(changes: list[Change], *, custom: bool) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{_name(change.observation, custom=custom)}</td>"
        f'<td align="center">'
        f"{_value(change.observation, change.previous, custom=custom)}</td>"
        f'<td align="center"><mark>'
        f"{_value(change.observation, change.current, custom=custom)}</mark>"
        "</td></tr>"
        for change in changes
    )
    return (
        "<table bordered striped compact>"
        "<tr><th>Проверка</th><th>Было</th><th>Стало</th></tr>"
        f"{rows}</table>"
    )


def _section(title: str, changes: list[Change], *, custom: bool) -> str:
    if not changes:
        return ""
    return f"<h4>{title}</h4>{_rows(changes, custom=custom)}"


def _snapshot(observations: list[Observation], *, custom: bool) -> str:
    shown = observations[:SNAPSHOT_LIMIT]
    rows = "".join(
        "<tr>"
        f"<td>{_name(o, custom=custom)}</td>"
        f"<td>{escape(o.source.value)}</td>"
        f'<td align="center">{_value(o, o.value, custom=custom)}</td>'
        "</tr>"
        for o in shown
    )
    hidden = len(observations) - len(shown)
    tail = f"<footer>и ещё {hidden}</footer>" if hidden else ""
    return (
        f"<details><summary>Все проверки ноды ({len(observations)})</summary>"
        f"<table striped compact>{rows}</table>{tail}</details>"
    )


def format_html(result: NodeReport, *, custom_emoji: bool = True) -> str:
    custom = custom_emoji
    countries = [
        c for c in result.changes if c.observation.kind is CheckKind.COUNTRY
    ]
    availability = [
        c for c in result.changes if c.observation.kind is not CheckKind.COUNTRY
    ]

    geo_title = f"{emoji.GEO.html(custom=custom)} География"
    access_title = f"{emoji.AVAILABILITY.html(custom=custom)} Доступность"
    body = (
        f"<h3>{_icon(result.changes, custom=custom)} "
        f"{escape(result.node_name)}</h3>"
        f'<p><tg-time unix="{int(time.time())}" format="r">сейчас'
        f"</tg-time></p>"
        f"{_section(geo_title, countries, custom=custom)}"
        f"{_section(access_title, availability, custom=custom)}"
    )
    snapshot = _snapshot(result.observations, custom=custom)
    if len(body) + len(snapshot) <= MAX_LENGTH:
        body += snapshot
    return body[:MAX_LENGTH]

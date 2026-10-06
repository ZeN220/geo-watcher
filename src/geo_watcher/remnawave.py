import ipaddress
import logging
import re
from urllib.parse import urlsplit

import httpx
from remnawave import AsyncRemnawave
from remnawave.exceptions import (
    ForbiddenError,
    NetworkError,
    RequestTimeoutError,
    UnauthorizedError,
)
from remnawave.http import HttpxAsync
from remnawave.types import GeocheckByNodeBody, Node

from geo_watcher.config import Geocheck
from geo_watcher.report import GeocheckReport, load_report

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1
JOB_TIMEOUT = 60

# First Remnawave Node release with geocheck support
MIN_NODE_VERSION = (3, 3, 0)

# For HTTP requests
PROXY_HEADERS = {
    "X-Forwarded-Proto": "https",
    "X-Forwarded-For": "127.0.0.1",
}


class GeocheckError(Exception):
    pass


class AccessError(Exception):
    pass


def create_sdk(base_url: str, token: str) -> AsyncRemnawave:
    return AsyncRemnawave(
        base_url=base_url,
        token=token,
        transport=HttpxAsync(
            httpx.AsyncClient(headers=panel_headers(base_url)),
        ),
    )


def panel_headers(base_url: str) -> dict[str, str]:
    if urlsplit(base_url).scheme.lower() == "http":
        return dict(PROXY_HEADERS)
    return {}


class RemnawaveGeocheck:
    def __init__(self, sdk: AsyncRemnawave, settings: Geocheck | None = None):
        self._sdk = sdk
        self._settings = settings or Geocheck()

    async def check_access(self) -> None:
        try:
            await self._sdk.nodes.get_nodes()
        except UnauthorizedError as error:
            raise AccessError("token is invalid or expired") from error
        except ForbiddenError as error:
            raise AccessError(
                "token lacks the permission to read nodes",
            ) from error
        except (NetworkError, RequestTimeoutError) as error:
            raise AccessError(
                "cannot connect to the Remnawave panel; check the configured "
                "base_url, DNS, and network connectivity",
            ) from error

    async def get_active_nodes(self) -> list[Node]:
        nodes = await self._sdk.nodes.get_nodes()
        active: list[Node] = []
        for node in nodes:
            if not node.is_connected or node.is_disabled:
                logger.debug(
                    "Node %s: skipped (connected=%s, disabled=%s)",
                    node.name,
                    node.is_connected,
                    node.is_disabled,
                )
                continue
            if not supports_geocheck(node):
                logger.warning(
                    "Node %s: skipped, node version %s does not support "
                    "geocheck (requires %s+)",
                    node.name,
                    node.versions.node if node.versions else "unknown",
                    ".".join(map(str, MIN_NODE_VERSION)),
                )
                continue
            active.append(node)
        return active

    async def run(self, node: Node) -> GeocheckReport:
        bind_to = self._settings.interface_for(node.name)
        logger.debug(
            "Node %s: geocheck bound to %s",
            node.name,
            bind_to or "default route",
        )
        result = await self._sdk.connections.wait_geocheck_by_node(
            node.uuid,
            _geocheck_body(bind_to),
            interval=POLL_INTERVAL,
            timeout=JOB_TIMEOUT,
        )
        if not result.success:
            raise GeocheckError(result.message or "geocheck was not successful")
        if result.raw_report is None:
            raise GeocheckError("empty raw_report")
        logger.debug("Node %s: raw report %s", node.name, result.raw_report)
        return load_report(result.raw_report)


def supports_geocheck(node: Node) -> bool:
    if node.versions is None:
        return True
    version = _parse_version(node.versions.node)
    if version is None:
        return True
    return version >= MIN_NODE_VERSION


def _parse_version(raw: str) -> tuple[int, ...] | None:
    match = re.match(r"v?(\d+)\.(\d+)(?:\.(\d+))?", raw.strip())
    if match is None:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _geocheck_body(bind_to: str | None) -> GeocheckByNodeBody:
    if bind_to is None:
        return GeocheckByNodeBody()
    try:
        ipaddress.ip_address(bind_to)
    except ValueError:
        return GeocheckByNodeBody(interface=bind_to)
    return GeocheckByNodeBody(ip=bind_to)

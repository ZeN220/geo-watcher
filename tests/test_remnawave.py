import uuid
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from remnawave.exceptions import (
    ForbiddenError,
    NetworkError,
    RequestTimeoutError,
    UnauthorizedError,
)
from remnawave.types import GeocheckByNodeBody, GeocheckByNodeResultResult

from geo_watcher.config import Geocheck
from geo_watcher.remnawave import (
    JOB_TIMEOUT,
    POLL_INTERVAL,
    PROXY_HEADERS,
    AccessError,
    GeocheckError,
    RemnawaveGeocheck,
    panel_headers,
    supports_geocheck,
)
from geo_watcher.report import GeocheckReport

NODE = cast("Any", SimpleNamespace(uuid=uuid.uuid4(), name="nl-1"))


class StubConnections:
    def __init__(self, result: GeocheckByNodeResultResult) -> None:
        self.result = result
        self.calls: list[tuple[UUID, float, float | None]] = []
        self.bodies: list[GeocheckByNodeBody] = []

    async def wait_geocheck_by_node(
        self,
        node_uuid: UUID,
        body: GeocheckByNodeBody,
        *,
        interval: float,
        timeout: float | None,  # noqa: ASYNC109 — сигнатура клиента
    ) -> GeocheckByNodeResultResult:
        self.calls.append((node_uuid, interval, timeout))
        self.bodies.append(body)
        return self.result


def _geocheck(
    connections: StubConnections,
    settings: Geocheck | None = None,
) -> RemnawaveGeocheck:
    sdk = cast("Any", SimpleNamespace(connections=connections))
    return RemnawaveGeocheck(sdk, settings)


def _result(
    *,
    success: bool = True,
    raw_report: dict[str, Any] | None = None,
    message: str | None = None,
) -> GeocheckByNodeResultResult:
    return GeocheckByNodeResultResult(
        success=success,
        node_uuid=NODE.uuid,
        image=None,
        raw_report=raw_report,
        message=message,
    )


async def test_run_returns_raw_report_and_passes_timings():
    connections = StubConnections(_result(raw_report={"schema": 1}))

    report = await _geocheck(connections).run(NODE)

    assert report == GeocheckReport(schema=1)
    assert connections.calls == [(NODE.uuid, POLL_INTERVAL, JOB_TIMEOUT)]
    assert connections.bodies == [GeocheckByNodeBody()]


@pytest.mark.parametrize(
    ("settings", "body"),
    [
        (Geocheck(interface="eth0"), GeocheckByNodeBody(interface="eth0")),
        (
            Geocheck(interface="eth0", node_interfaces={"nl-1": "wg0"}),
            GeocheckByNodeBody(interface="wg0"),
        ),
        (
            Geocheck(interface="203.0.113.7"),
            GeocheckByNodeBody(ip="203.0.113.7"),
        ),
        (
            Geocheck(interface="2001:db8::1"),
            GeocheckByNodeBody(ip="2001:db8::1"),
        ),
        (Geocheck(node_interfaces={"de-1": "wg0"}), GeocheckByNodeBody()),
    ],
)
async def test_run_binds_to_configured_interface_or_ip(
    settings: Geocheck,
    body: GeocheckByNodeBody,
):
    connections = StubConnections(_result(raw_report={"schema": 1}))

    await _geocheck(connections, settings).run(NODE)

    assert connections.bodies == [body]


async def test_run_raises_when_not_successful():
    connections = StubConnections(
        _result(success=False, message="node is offline"),
    )

    with pytest.raises(GeocheckError, match="node is offline"):
        await _geocheck(connections).run(NODE)


async def test_run_raises_on_empty_report():
    connections = StubConnections(_result())

    with pytest.raises(GeocheckError, match="empty raw_report"):
        await _geocheck(connections).run(NODE)


class StubNodes:
    def __init__(
        self,
        error: Exception | None = None,
        nodes: list[Any] | None = None,
    ) -> None:
        self.error = error
        self.nodes = nodes or []

    async def get_nodes(self) -> list[Any]:
        if self.error is not None:
            raise self.error
        return self.nodes


def _with_nodes(nodes: StubNodes) -> RemnawaveGeocheck:
    return RemnawaveGeocheck(cast("Any", SimpleNamespace(nodes=nodes)))


async def test_check_access_passes_when_nodes_are_readable():
    await _with_nodes(StubNodes()).check_access()


async def test_check_access_reports_missing_permission():
    forbidden = ForbiddenError("Forbidden", status=403)

    with pytest.raises(AccessError, match="permission to read nodes"):
        await _with_nodes(StubNodes(forbidden)).check_access()


async def test_check_access_reports_invalid_token():
    unauthorized = UnauthorizedError("Unauthorized", status=401)

    with pytest.raises(AccessError, match="invalid or expired"):
        await _with_nodes(StubNodes(unauthorized)).check_access()


@pytest.mark.parametrize(
    "error",
    [NetworkError("Name or service not known"), RequestTimeoutError("timeout")],
)
async def test_check_access_reports_connection_failure(error: Exception):
    with pytest.raises(AccessError, match="check the configured base_url"):
        await _with_nodes(StubNodes(error)).check_access()


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://remnawave:3000", PROXY_HEADERS),
        ("HTTP://remnawave:3000", PROXY_HEADERS),
        ("https://panel.example.com", {}),
    ],
)
def test_panel_headers(base_url: str, expected: dict[str, str]) -> None:
    assert panel_headers(base_url) == expected


def _node(
    name: str,
    version: str | None = "3.4.0",
    *,
    connected: bool = True,
    disabled: bool = False,
) -> Any:
    versions = None
    if version is not None:
        versions = SimpleNamespace(node=version, xray="25.10.15")
    return SimpleNamespace(
        name=name,
        is_connected=connected,
        is_disabled=disabled,
        versions=versions,
    )


async def test_get_active_nodes_skips_unsupported_versions():
    nodes = [
        _node("new"),
        _node("old", "3.2.2"),
        _node("offline", connected=False),
        _node("disabled", disabled=True),
    ]

    active = await _with_nodes(StubNodes(nodes=nodes)).get_active_nodes()

    assert [node.name for node in active] == ["new"]


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("3.3.0", True),
        ("3.4.2", True),
        ("v3.3.1", True),
        ("4.0", True),
        ("3.3.0-dev", True),
        ("3.2.2", False),
        ("2.7.0", False),
        ("unknown", True),
        (None, True),
    ],
)
def test_supports_geocheck(version: str | None, expected: bool) -> None:  # noqa: FBT001
    assert supports_geocheck(_node("nl-1", version)) is expected

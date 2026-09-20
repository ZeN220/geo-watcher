import uuid
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from remnawave.exceptions import ForbiddenError, UnauthorizedError
from remnawave.types import GeocheckByNodeBody, GeocheckByNodeResultResult

from geo_watcher.remnawave import (
    JOB_TIMEOUT,
    POLL_INTERVAL,
    AccessError,
    GeocheckError,
    RemnawaveGeocheck,
)
from geo_watcher.report import GeocheckReport

NODE = cast("Any", SimpleNamespace(uuid=uuid.uuid4(), name="nl-1"))


class StubConnections:
    def __init__(self, result: GeocheckByNodeResultResult) -> None:
        self.result = result
        self.calls: list[tuple[UUID, float, float | None]] = []

    async def wait_geocheck_by_node(
        self,
        node_uuid: UUID,
        body: GeocheckByNodeBody,  # noqa: ARG002
        *,
        interval: float,
        timeout: float | None,  # noqa: ASYNC109 — сигнатура клиента
    ) -> GeocheckByNodeResultResult:
        self.calls.append((node_uuid, interval, timeout))
        return self.result


def _geocheck(connections: StubConnections) -> RemnawaveGeocheck:
    sdk = cast("Any", SimpleNamespace(connections=connections))
    return RemnawaveGeocheck(sdk)


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
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def get_nodes(self) -> list[Any]:
        if self.error is not None:
            raise self.error
        return []


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

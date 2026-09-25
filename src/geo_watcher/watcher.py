import asyncio
import logging
import time

from remnawave.types import Node

from geo_watcher.analysis import NodeReport, analyze, merge_state
from geo_watcher.remnawave import RemnawaveGeocheck
from geo_watcher.report import Source, parse_observations
from geo_watcher.state import State, StateStore
from geo_watcher.telegram import Notifier

logger = logging.getLogger(__name__)

MAX_CONCURRENT_CHECKS = 3


class GeoWatcher:
    def __init__(
        self,
        geocheck: RemnawaveGeocheck,
        store: StateStore,
        notifier: Notifier,
        sources: list[Source],
    ):
        self._geocheck = geocheck
        self._store = store
        self._notifier = notifier
        self._sources = sources
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

    async def check_access(self) -> None:
        await self._geocheck.check_access()

    async def run_once(self) -> list[NodeReport]:
        nodes = await self._geocheck.get_active_nodes()
        logger.info(
            "Checking %d nodes: %s",
            len(nodes),
            ", ".join(node.name for node in nodes) or "none",
        )

        state = self._store.load()
        results = await asyncio.gather(
            *(self._check_node(node, state) for node in nodes),
        )
        self._store.save(state)
        return [r for r in results if r is not None]

    async def _check_node(
        self,
        node: Node,
        state: State,
    ) -> NodeReport | None:
        async with self._semaphore:
            logger.debug("Node %s: geocheck started", node.name)
            started = time.monotonic()
            try:
                report = await self._geocheck.run(node)
            except Exception:
                logger.exception("Node %s: geocheck failed", node.name)
                return None
            logger.debug(
                "Node %s: geocheck finished in %.1f s",
                node.name,
                time.monotonic() - started,
            )

        key = str(node.uuid)
        previous = state.get(key, {})
        observations = parse_observations(report, self._sources)
        result = analyze(node.name, observations, previous)
        state[key] = merge_state(previous, observations)
        log_result(result)
        if result.changes:
            try:
                await self._notifier.notify(result)
            except Exception:
                logger.exception(
                    "Node %s: failed to send notification", node.name
                )
        return result


def log_result(result: NodeReport) -> None:
    if not result.observations:
        logger.warning("Node %s: no checks in the report", result.node_name)
        return

    if not result.changes:
        logger.info(
            "Node %s: no changes in %d checks",
            result.node_name,
            len(result.observations),
        )
        return

    logger.warning(
        "Node %s: checks changed since the last run:\n%s",
        result.node_name,
        "\n".join(
            f"  - {c.observation.label}: {c.previous} → {c.current}"
            for c in result.changes
        ),
    )

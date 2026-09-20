"""
Usage:
    geo-watcher
    geo-watcher --once
    geo-watcher --config /path/to/config.toml
"""

import argparse
import asyncio
import logging
from collections.abc import Sequence

import httpx
from remnawave import AsyncRemnawave

from geo_watcher.config import Config, ConfigError
from geo_watcher.remnawave import AccessError, RemnawaveGeocheck
from geo_watcher.state import StateStore
from geo_watcher.telegram import Notifier, NullNotifier, TelegramNotifier
from geo_watcher.watcher import GeoWatcher

logger = logging.getLogger("geo_watcher")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args(argv)


def create_notifier(config: Config, client: httpx.AsyncClient) -> Notifier:
    if config.telegram is None:
        logger.warning(
            "No [telegram] section in config, notifications are disabled"
        )
        return NullNotifier()
    return TelegramNotifier(
        client,
        bot_token=config.telegram.bot_token,
        chat_id=config.telegram.chat_id,
        message_thread_id=config.telegram.message_thread_id,
    )


async def run(config: Config, *, once: bool) -> None:
    async with (
        AsyncRemnawave(
            base_url=config.remnawave.base_url,
            token=config.remnawave.token,
        ) as sdk,
        httpx.AsyncClient(timeout=30) as http,
    ):
        watcher = GeoWatcher(
            geocheck=RemnawaveGeocheck(sdk),
            store=StateStore(config.watcher.state_file),
            notifier=create_notifier(config, http),
            sources=config.watcher.sources,
            concurrency=config.watcher.concurrency,
        )
        try:
            await watcher.check_access()
        except AccessError as error:
            logger.error("Remnawave access check failed: %s", error)  # noqa: TRY400
            raise SystemExit(1) from error

        while True:
            try:
                await watcher.run_once()
            except Exception:
                if once:
                    raise
                logger.exception("Run failed")
            if once:
                return
            logger.info("Next run in %d s", config.watcher.interval)
            await asyncio.sleep(config.watcher.interval)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        config = Config.from_file(args.config)
    except ConfigError as error:
        raise SystemExit(str(error)) from error
    logging.basicConfig(
        level=config.logging.level,
        format=config.logging.format,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    asyncio.run(run(config, once=args.once))


if __name__ == "__main__":
    main()

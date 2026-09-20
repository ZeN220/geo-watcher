from pathlib import Path

import pytest

from geo_watcher.config import Config, ConfigError, Logging, Watcher
from geo_watcher.report import Source

MINIMAL = """
[remnawave]
base_url = "https://panel"
token = "secret"
"""

FULL = """
[remnawave]
base_url = "https://panel"
token = "secret"

[telegram]
bot_token = "123:ABC"
chat_id = "@my_channel"
message_thread_id = 42

[watcher]
interval = 600
sources = ["services", "cdn"]
"""

BROKEN = """
[remnawave]
base_url = "https://panel"

[watcher]
interval = "often"
sources = ["services", "servises"]
"""


def _write(tmp_path: Path, body: str) -> str:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_optional_sections_fall_back_to_defaults(tmp_path: Path):
    config = Config.from_file(_write(tmp_path, MINIMAL))

    assert config.telegram is None
    assert config.watcher == Watcher()
    assert config.logging == Logging()


def test_full_config_is_loaded(tmp_path: Path):
    config = Config.from_file(_write(tmp_path, FULL))

    assert config.telegram is not None
    assert config.telegram.chat_id == "@my_channel"
    assert config.telegram.message_thread_id == 42
    assert config.watcher.interval == 600
    assert config.watcher.sources == [Source.SERVICES, Source.CDN]
    assert config.watcher.state_file == "state.json"


def test_every_problem_is_reported_with_its_path(tmp_path: Path):
    with pytest.raises(ConfigError) as error:
        Config.from_file(_write(tmp_path, BROKEN))

    assert str(error.value).splitlines()[1:] == [
        "  remnawave: missing required fields: token",
        "  watcher.interval: expected int, got 'often'",
        (
            "  watcher.sources.1: expected any of: "
            "services, geoip, cdn, stash; got 'servises'"
        ),
    ]

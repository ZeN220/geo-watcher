from pathlib import Path

import pytest

from geo_watcher.config import (
    Config,
    ConfigError,
    Geocheck,
    Logging,
    Watcher,
)
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

[watcher.excluded_checks]
"nl-*" = ["netflix_access"]

[geocheck]
interface = "eth0"

[geocheck.node_interfaces]
"nl-*" = "ens3"
"nl-1" = "wg0"
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
    assert config.geocheck == Geocheck()
    assert config.logging == Logging()


def test_full_config_is_loaded(tmp_path: Path):
    config = Config.from_file(_write(tmp_path, FULL))

    assert config.telegram is not None
    assert config.telegram.chat_id == "@my_channel"
    assert config.telegram.message_thread_id == 42
    assert config.watcher.interval == 600
    assert config.watcher.sources == [Source.SERVICES, Source.CDN]
    assert config.watcher.state_file == "state.json"
    assert config.watcher.excluded_checks == {"nl-*": ["netflix_access"]}
    assert config.geocheck.interface_for("nl-1") == "wg0"
    assert config.geocheck.interface_for("nl-2") == "ens3"
    assert config.geocheck.interface_for("de-1") == "eth0"


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


@pytest.mark.parametrize(
    ("node_name", "interface"),
    [
        ("nl-1", "wg0"),
        ("nl-2", "ens3"),
        ("NL-2", "eth0"),
        ("de-10", "ens4"),
        ("de-1", "ens5"),
        ("fi-1", "eth0"),
        ("us-1", "ens6"),
        ("us-2", "ens6"),
        ("us-3", "eth0"),
        ("nl-3", None),
        ("se-1", None),
        ("se-2", None),
    ],
)
def test_node_interface_resolution(node_name: str, interface: str | None):
    geocheck = Geocheck(
        interface="eth0",
        node_interfaces={
            "nl-*": "ens3",
            "de-1?": "ens4",
            "de-*": "ens5",
            "nl-1": "wg0",
            "nl-3": "",
            "us-[12]": "ens6",
            "se-*": "  ",
        },
    )

    assert geocheck.interface_for(node_name) == interface


@pytest.mark.parametrize("interface", ["", "  "])
def test_empty_interface_means_default_route(interface: str):
    assert Geocheck(interface=interface).interface_for("nl-1") is None

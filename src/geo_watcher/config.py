import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from adaptix import Retort
from adaptix.load_error import (
    BadVariantLoadError,
    LoadError,
    NoRequiredFieldsLoadError,
    TypeLoadError,
)
from adaptix.struct_trail import Trail, get_trail

from geo_watcher.report import Source


class ConfigError(Exception):
    pass


@dataclass
class Remnawave:
    base_url: str
    token: str


@dataclass
class Telegram:
    bot_token: str
    chat_id: int | str
    message_thread_id: int | None = None
    custom_emoji: bool = True


@dataclass
class Watcher:
    interval: int = 3600
    concurrency: int = 3
    sources: list[Source] = field(
        default_factory=lambda: [Source.SERVICES, Source.GEOIP, Source.STASH],
    )
    state_file: str = "state.json"


@dataclass
class Logging:
    level: int = 20
    format: str = "[%(levelname)s] %(asctime)s - %(name)s - %(message)s"


_retort = Retort()


@dataclass
class Config:
    remnawave: Remnawave
    watcher: Watcher = field(default_factory=Watcher)
    logging: Logging = field(default_factory=Logging)
    telegram: Telegram | None = None

    @classmethod
    def from_file(cls, filename: str) -> "Config":
        data = tomllib.loads(Path(filename).read_text(encoding="utf-8"))
        try:
            return _retort.load(data, cls)
        except LoadError as error:
            raise ConfigError(_describe(filename, error)) from error


def _describe(filename: str, error: LoadError) -> str:
    problems = "\n".join(
        f"  {'.'.join(map(str, trail)) or filename}: {_explain(problem)}"
        for trail, problem in _problems(error)
    )
    return f"{filename} is invalid:\n{problems}"


def _explain(problem: BaseException) -> str:
    match problem:
        case NoRequiredFieldsLoadError():
            missing = ", ".join(sorted(problem.fields))
            return f"missing required fields: {missing}"
        case TypeLoadError():
            expected = getattr(problem.expected_type, "__name__", "")
            return f"expected {expected}, got {problem.input_value!r}"
        case BadVariantLoadError():
            allowed = ", ".join(map(str, problem.allowed_values))
            return f"expected any of: {allowed}; got {problem.input_value!r}"
        case _:
            return str(problem)


def _problems(
    error: BaseException,
    prefix: Trail = (),
) -> Iterator[tuple[Trail, BaseException]]:
    trail = (*prefix, *get_trail(error))
    if isinstance(error, BaseExceptionGroup):
        for sub in error.exceptions:
            yield from _problems(sub, trail)
    else:
        yield trail, error

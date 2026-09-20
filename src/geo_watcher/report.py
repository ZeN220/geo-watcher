"""
"geo": {
    "services": [
        {"id": "google", "name": "Google", "kind": "country",
         "ipv4": {"value": "NL", "country": "Netherlands"},
         "ipv6": {"error": "..."}},
        {"id": "reddit_guest", "name": "Reddit guest access",
         "kind": "availability", "ipv4": {"value": "yes"}},
        ...
    ],
    "geoip": [...],
    "cdn": [...]
},
"stash_checks": [
    {"id": "netflix_access", "name": "Netflix", "state": "restricted",
     "region": "US", "detail": "Originals only", "rtt_ms": 120.5},
    ...
]
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any

from adaptix import Chain, Retort, loader


class Source(StrEnum):
    SERVICES = "services"
    GEOIP = "geoip"
    CDN = "cdn"
    STASH = "stash"


class Family(StrEnum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class CheckKind(StrEnum):
    COUNTRY = "country"
    AVAILABILITY = "availability"
    BLOCKED = "blocked"

    UNKNOWN = "unknown"


class StashState(StrEnum):
    AVAILABLE = "available"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"

    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class GeocheckValue:
    value: str | None = None
    country: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class GeocheckCheck:
    id: str
    name: str
    kind: CheckKind
    # нет, если семейство адресов пропущено
    ipv4: GeocheckValue | None = None
    ipv6: GeocheckValue | None = None

    def family(self, family: Family) -> GeocheckValue | None:
        return self.ipv6 if family is Family.IPV6 else self.ipv4


@dataclass(frozen=True, slots=True)
class GeocheckGeo:
    services: list[GeocheckCheck] = field(default_factory=list)
    geoip: list[GeocheckCheck] = field(default_factory=list)
    cdn: list[GeocheckCheck] = field(default_factory=list)

    def group(self, source: Source) -> list[GeocheckCheck]:
        return getattr(self, source.value)


@dataclass(frozen=True, slots=True)
class StashCheck:
    id: str
    name: str
    state: StashState
    region: str | None = None
    detail: str | None = None
    rtt_ms: float | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class GeocheckReport:
    schema: int
    geo: GeocheckGeo | None = None
    stash_checks: list[StashCheck] = field(default_factory=list)


def _known_or[E: Enum](enum: type[E], unknown: E) -> Callable[[Any], E]:
    def load(data: Any) -> E:
        try:
            return enum(data)
        except ValueError:
            return unknown

    return load


_retort = Retort(
    recipe=[
        loader(list, lambda data: [] if data is None else data, Chain.FIRST),
        loader(CheckKind, _known_or(CheckKind, CheckKind.UNKNOWN)),
        loader(StashState, _known_or(StashState, StashState.UNKNOWN)),
    ],
)


def load_report(raw_report: dict[str, Any]) -> GeocheckReport:
    return _retort.load(raw_report, GeocheckReport)


@dataclass(frozen=True, slots=True)
class Observation:
    source: Source
    id: str
    name: str
    family: Family | None
    # "NL" для страны, "yes"/"no" для доступности, "available (US)" для stash
    value: str

    @property
    def key(self) -> str:
        parts = [self.source.value, self.id]
        if self.family is not None:
            parts.append(self.family)
        return "/".join(parts)

    @property
    def label(self) -> str:
        where = self.source.value
        if self.family is not None:
            where = f"{self.source.value}, {self.family.value}"
        return f"{self.name} ({where})"


def parse_observations(
    report: GeocheckReport,
    sources: Iterable[Source],
) -> list[Observation]:
    result: list[Observation] = []
    for source in sources:
        if source is Source.STASH:
            result += _stash_observations(report)
        else:
            result += _geo_observations(report, source)
    return result


def _geo_observations(
    report: GeocheckReport,
    source: Source,
) -> list[Observation]:
    if report.geo is None:
        return []
    result: list[Observation] = []
    for check in report.geo.group(source):
        for family in Family:
            outcome = check.family(family)
            if outcome is None or outcome.error or not outcome.value:
                continue
            # страна приходит ISO-кодом, availability/blocked — yes/no
            value = outcome.value
            result.append(
                Observation(
                    source=source,
                    id=check.id,
                    name=check.name,
                    family=family,
                    value=value.upper()
                    if check.kind is CheckKind.COUNTRY
                    else value.lower(),
                ),
            )
    return result


def _stash_observations(report: GeocheckReport) -> list[Observation]:
    result: list[Observation] = []
    for check in report.stash_checks:
        if check.state is StashState.ERROR or check.error:
            continue
        value = check.state.value
        if check.region:
            value = f"{value} ({check.region.upper()})"
        result.append(
            Observation(
                source=Source.STASH,
                id=check.id,
                name=check.name,
                family=None,
                value=value,
            ),
        )
    return result

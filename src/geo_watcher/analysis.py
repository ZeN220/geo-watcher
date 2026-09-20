from dataclasses import dataclass

from geo_watcher.report import Observation


@dataclass(frozen=True, slots=True)
class Change:
    observation: Observation
    previous: str

    @property
    def current(self) -> str:
        return self.observation.value


@dataclass(frozen=True, slots=True)
class NodeReport:
    node_name: str
    observations: list[Observation]
    changes: list[Change]


def analyze(
    node_name: str,
    observations: list[Observation],
    previous: dict[str, str],
) -> NodeReport:
    changes = [
        Change(observation=o, previous=previous[o.key])
        for o in observations
        if o.key in previous and previous[o.key] != o.value
    ]
    return NodeReport(
        node_name=node_name,
        observations=observations,
        changes=changes,
    )


def merge_state(
    previous: dict[str, str],
    observations: list[Observation],
) -> dict[str, str]:
    return previous | {o.key: o.value for o in observations}

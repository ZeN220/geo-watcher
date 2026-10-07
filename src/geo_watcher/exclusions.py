from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from geo_watcher.report import Observation


@dataclass(frozen=True, slots=True)
class CheckExclusions:
    rules: dict[str, list[str]] = field(default_factory=dict)

    def excludes(self, node_name: str, observation: Observation) -> bool:
        for node_pattern, patterns in self.rules.items():
            if not fnmatchcase(node_name, node_pattern):
                continue
            for pattern in patterns:
                if fnmatchcase(observation.id, pattern):
                    return True
                if fnmatchcase(observation.name, pattern):
                    return True
        return False

    def apply(
        self,
        node_name: str,
        observations: list[Observation],
    ) -> list[Observation]:
        return [o for o in observations if not self.excludes(node_name, o)]

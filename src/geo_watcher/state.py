import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

State = dict[str, dict[str, str]]


class StateStore:
    def __init__(self, path: str):
        self._path = Path(path)

    def load(self) -> State:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception(
                "Failed to read %s, starting from scratch", self._path
            )
            return {}

    def save(self, state: State) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self._path)

"""Read-only query surface over the most recent measurands."""

from __future__ import annotations

from .decode import Measurand


class MeasurandStore:
    """Last-value cache keyed by measurand name."""

    def __init__(self) -> None:
        self._latest: dict[str, Measurand] = {}

    def record(self, measurand: Measurand) -> None:
        current = self._latest.get(measurand.name)
        if current is None or measurand.timestamp >= current.timestamp:
            self._latest[measurand.name] = measurand

    def latest(self, name: str) -> Measurand | None:
        return self._latest.get(name)

    def names(self) -> list[str]:
        return sorted(self._latest)

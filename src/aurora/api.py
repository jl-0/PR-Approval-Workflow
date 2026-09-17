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

    def age_of(self, name: str, now: int) -> int | None:
        """Seconds since *name* last updated, or None if never seen.

        Returned alongside a value so a caller cannot mistake a stale reading
        for a current one — the difference between "nominal" and "we lost the
        link" is otherwise invisible.
        """
        measurand = self._latest.get(name)
        return None if measurand is None else now - measurand.timestamp

    def names(self) -> list[str]:
        return sorted(self._latest)

    def snapshot(self) -> dict[str, Measurand]:
        """Return every current value in one pass.

        Dashboards previously issued one lookup per measurand, which meant a
        read could observe a mix of values from either side of an update. A
        snapshot is taken from a single copy of the mapping instead.
        """
        return dict(self._latest)

    def stale(self, now: int, max_age: int) -> list[str]:
        """Names whose newest value is older than *max_age* seconds."""
        return sorted(
            name
            for name, measurand in self._latest.items()
            if now - measurand.timestamp > max_age
        )

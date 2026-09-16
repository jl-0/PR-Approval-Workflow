"""Frame intake with de-duplication and bounded buffering."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator

from .config import GatewayConfig


class FrameQueue:
    """A bounded FIFO that drops the oldest frame when full."""

    def __init__(self, config: GatewayConfig | None = None) -> None:
        self._config = config or GatewayConfig()
        self._frames: deque[bytes] = deque(maxlen=self._config.queue_depth)
        self._seen: set[bytes] = set()
        self.dropped = 0

    def offer(self, frame: bytes) -> bool:
        """Accept *frame*; return False if it was a duplicate."""
        if frame in self._seen:
            return False
        if len(self._frames) == self._frames.maxlen:
            self.dropped += 1
        self._seen.add(frame)
        self._frames.append(frame)
        return True

    def drain(self) -> Iterator[bytes]:
        while self._frames:
            yield self._frames.popleft()

    def __len__(self) -> int:
        return len(self._frames)

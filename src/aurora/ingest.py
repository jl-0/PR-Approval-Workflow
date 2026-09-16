"""Frame intake with de-duplication and bounded buffering."""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Iterator
from enum import Enum

from .config import GatewayConfig
from .decode import checksum_ok


class DropReason(str, Enum):
    """Why a frame did not reach the store.

    Discarded telemetry has to be accountable: an operator must be able to say
    why any gap in the record exists, not merely that one does.
    """

    DUPLICATE = "duplicate"
    CHECKSUM = "checksum"
    QUEUE_FULL = "queue_full"


class FrameQueue:
    """A bounded FIFO that drops the oldest frame when full."""

    def __init__(self, config: GatewayConfig | None = None) -> None:
        self._config = config or GatewayConfig()
        self._frames: deque[bytes] = deque(maxlen=self._config.queue_depth)
        # The dedupe window is bounded: an unbounded set grew for the lifetime
        # of the process and was the largest allocation in a long pass.
        self._seen_order: deque[bytes] = deque(maxlen=self._config.queue_depth)
        self._seen: set[bytes] = set()
        self.dropped = 0
        self.rejected = 0
        self.drops: Counter[DropReason] = Counter()

    def offer(self, frame: bytes) -> bool:
        """Accept *frame*; return False if it was rejected.

        A frame is rejected when it duplicates one already seen, or — under
        strict checksums — when its trailing sum does not verify. Rejected
        frames never reach the store.
        """
        if frame in self._seen:
            self.drops[DropReason.DUPLICATE] += 1
            return False
        if self._config.strict_checksums and not checksum_ok(frame):
            self.rejected += 1
            self.drops[DropReason.CHECKSUM] += 1
            return False
        if len(self._frames) == self._frames.maxlen:
            self.dropped += 1
            self.drops[DropReason.QUEUE_FULL] += 1
        self._remember(frame)
        self._frames.append(frame)
        return True

    def _remember(self, frame: bytes) -> None:
        """Record *frame* in the dedupe window, evicting the oldest entry."""
        if len(self._seen_order) == self._seen_order.maxlen:
            self._seen.discard(self._seen_order[0])
        self._seen_order.append(frame)
        self._seen.add(frame)

    def drain(self) -> Iterator[bytes]:
        while self._frames:
            yield self._frames.popleft()

    def __len__(self) -> int:
        return len(self._frames)

    def drop_report(self) -> dict[str, int]:
        """Every drop reason and its count, including reasons not yet seen.

        Reporting zeroes matters: a missing key reads as "not measured", a zero
        reads as "measured, none occurred".
        """
        return {reason.value: self.drops[reason] for reason in DropReason}

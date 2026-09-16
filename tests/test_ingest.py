from aurora.config import GatewayConfig
from aurora.ingest import FrameQueue


def test_duplicate_frames_are_rejected():
    queue = FrameQueue()
    assert queue.offer(b"abc") is True
    assert queue.offer(b"abc") is False
    assert len(queue) == 1


def test_queue_drops_oldest_when_full():
    queue = FrameQueue(GatewayConfig(queue_depth=2))
    for payload in (b"a", b"b", b"c"):
        queue.offer(payload)
    assert queue.dropped == 1
    assert list(queue.drain()) == [b"b", b"c"]


def checked(payload: bytes) -> bytes:
    import struct

    return payload + struct.pack(">H", sum(payload) & 0xFFFF)


def test_corrupt_frames_are_rejected_in_strict_mode():
    queue = FrameQueue(GatewayConfig(strict_checksums=True))
    assert queue.offer(b"not-a-valid-frame") is False
    assert queue.rejected == 1
    assert len(queue) == 0


def test_valid_frames_pass_strict_mode():
    queue = FrameQueue(GatewayConfig(strict_checksums=True))
    assert queue.offer(checked(b"\x00\x42\x00\x00\x00\x00\x00\x01")) is True
    assert queue.rejected == 0

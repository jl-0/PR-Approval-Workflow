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

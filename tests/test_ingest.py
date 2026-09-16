from aurora.config import GatewayConfig
from aurora.ingest import FrameQueue


def test_duplicate_frames_are_rejected():
    # These two predate checksum enforcement and use opaque payloads, so they
    # exercise the queue rather than the validator.
    queue = FrameQueue(GatewayConfig(strict_checksums=False))
    assert queue.offer(b"abc") is True
    assert queue.offer(b"abc") is False
    assert len(queue) == 1


def test_queue_drops_oldest_when_full():
    queue = FrameQueue(GatewayConfig(queue_depth=2, strict_checksums=False))
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


def test_drop_report_accounts_for_every_reason():
    queue = FrameQueue(GatewayConfig(queue_depth=1, strict_checksums=False))
    queue.offer(b"a")
    queue.offer(b"a")
    queue.offer(b"b")
    report = queue.drop_report()
    assert report["duplicate"] == 1
    assert report["queue_full"] == 1
    assert report["checksum"] == 0


def test_drop_report_lists_unseen_reasons_as_zero():
    queue = FrameQueue(GatewayConfig(strict_checksums=False))
    assert queue.drop_report() == {"duplicate": 0, "checksum": 0, "queue_full": 0}


def test_dedupe_window_is_bounded():
    queue = FrameQueue(GatewayConfig(queue_depth=2, strict_checksums=False))
    for payload in (b"a", b"b", b"c"):
        queue.offer(payload)
    # "a" has fallen out of the window, so it is no longer seen as a duplicate.
    assert queue.offer(b"a") is True
    assert queue.offer(b"c") is False


def test_discard_summary_reports_count_and_proportion():
    queue = FrameQueue(GatewayConfig(queue_depth=4, strict_checksums=False))
    for payload in (b"a", b"a", b"b", b"c"):
        queue.offer(payload)
    summary = queue.discard_summary()
    assert summary["offered"] == 4
    assert summary["discarded"] == 1
    assert summary["proportion"] == 0.25
    assert summary["by_reason"]["duplicate"] == 1


def test_discard_summary_on_an_idle_queue_does_not_divide_by_zero():
    summary = FrameQueue().discard_summary()
    assert summary == {
        "offered": 0,
        "discarded": 0,
        "proportion": 0.0,
        "by_reason": {"duplicate": 0, "checksum": 0, "queue_full": 0},
    }

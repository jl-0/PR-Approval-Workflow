import pytest

from aurora.config import ConfigError, GatewayConfig


def test_defaults_are_valid():
    assert GatewayConfig().queue_depth > 0


@pytest.mark.parametrize("depth", [0, -1])
def test_invalid_queue_depth_is_rejected(depth):
    with pytest.raises(ConfigError, match="queue_depth"):
        GatewayConfig(queue_depth=depth)


def test_invalid_frame_size_is_rejected():
    with pytest.raises(ConfigError, match="frame_bytes"):
        GatewayConfig(frame_bytes=0)

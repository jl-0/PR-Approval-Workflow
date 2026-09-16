"""Runtime configuration for the gateway."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_QUEUE_DEPTH = 2048
DEFAULT_FRAME_BYTES = 1115


class ConfigError(ValueError):
    """Raised when the environment describes an unusable gateway."""


@dataclass(frozen=True)
class GatewayConfig:
    """Values read once at process start."""

    queue_depth: int = DEFAULT_QUEUE_DEPTH
    frame_bytes: int = DEFAULT_FRAME_BYTES
    strict_checksums: bool = True

    def __post_init__(self) -> None:
        # A zero-depth queue discards every frame, which used to start cleanly
        # and look healthy. Fail at start-up instead.
        if self.queue_depth < 1:
            raise ConfigError(f"queue_depth must be at least 1, got {self.queue_depth}")
        if self.frame_bytes < 1:
            raise ConfigError(f"frame_bytes must be at least 1, got {self.frame_bytes}")

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        return cls(
            queue_depth=int(os.environ.get("AURORA_QUEUE_DEPTH", DEFAULT_QUEUE_DEPTH)),
            frame_bytes=int(os.environ.get("AURORA_FRAME_BYTES", DEFAULT_FRAME_BYTES)),
            strict_checksums=os.environ.get("AURORA_STRICT_CHECKSUMS", "1") == "1",
        )

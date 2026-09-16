"""Runtime configuration for the gateway."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_QUEUE_DEPTH = 2048
DEFAULT_FRAME_BYTES = 1115


@dataclass(frozen=True)
class GatewayConfig:
    """Values read once at process start."""

    queue_depth: int = DEFAULT_QUEUE_DEPTH
    frame_bytes: int = DEFAULT_FRAME_BYTES
    strict_checksums: bool = True

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        return cls(
            queue_depth=int(os.environ.get("AURORA_QUEUE_DEPTH", DEFAULT_QUEUE_DEPTH)),
            frame_bytes=int(os.environ.get("AURORA_FRAME_BYTES", DEFAULT_FRAME_BYTES)),
            strict_checksums=os.environ.get("AURORA_STRICT_CHECKSUMS", "1") == "1",
        )

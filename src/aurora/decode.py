"""Decode raw telemetry frames into named measurands."""

from __future__ import annotations

import struct
from dataclasses import dataclass

HEADER = struct.Struct(">HHI")
APID_MASK = 0x07FF


@dataclass(frozen=True)
class Measurand:
    name: str
    value: float
    timestamp: int


class DecodeError(ValueError):
    """Raised when a frame cannot be interpreted."""


def apid_of(frame: bytes) -> int:
    """Return the application process identifier carried by *frame*."""
    if len(frame) < HEADER.size:
        raise DecodeError(f"frame too short: {len(frame)} bytes")
    identifier, _sequence, _time = HEADER.unpack_from(frame)
    return identifier & APID_MASK


def decode(frame: bytes, dictionary: dict[int, str]) -> Measurand:
    """Decode a single frame using *dictionary* to name the measurand."""
    apid = apid_of(frame)
    name = dictionary.get(apid)
    if name is None:
        raise DecodeError(f"no dictionary entry for APID {apid}")
    _identifier, _sequence, timestamp = HEADER.unpack_from(frame)
    (value,) = struct.unpack_from(">f", frame, HEADER.size)
    return Measurand(name=name, value=value, timestamp=timestamp)

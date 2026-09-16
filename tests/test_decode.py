import struct

import pytest

from aurora.decode import DecodeError, Measurand, apid_of, decode


def frame(apid: int, value: float, timestamp: int = 1_700_000_000) -> bytes:
    return struct.pack(">HHI", apid, 0, timestamp) + struct.pack(">f", value)


def test_apid_is_masked():
    assert apid_of(frame(0x0042, 1.0)) == 0x42


def test_decode_returns_named_measurand():
    result = decode(frame(0x0042, 12.5), {0x42: "bus_voltage"})
    assert result == Measurand(name="bus_voltage", value=12.5, timestamp=1_700_000_000)


def test_short_frame_is_rejected():
    with pytest.raises(DecodeError):
        apid_of(b"\x00")


def test_unknown_apid_is_rejected():
    with pytest.raises(DecodeError):
        decode(frame(0x0099, 1.0), {})

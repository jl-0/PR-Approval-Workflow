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


def checked(payload: bytes) -> bytes:
    return payload + struct.pack(">H", sum(payload) & 0xFFFF)


def test_checksum_accepts_a_well_formed_frame():
    from aurora.decode import checksum_ok

    assert checksum_ok(checked(frame(0x42, 1.0))) is True


def test_checksum_rejects_a_corrupted_frame():
    from aurora.decode import checksum_ok

    corrupt = bytearray(checked(frame(0x42, 1.0)))
    corrupt[4] ^= 0xFF
    assert checksum_ok(bytes(corrupt)) is False


def test_checksum_rejects_a_truncated_frame():
    from aurora.decode import checksum_ok

    assert checksum_ok(b"\x00\x01") is False


def test_high_payload_apid_decodes():
    result = decode(frame(0x0512, 3.5), {0x512: "payload_temp"})
    assert result.name == "payload_temp"


def test_dictionary_keyed_on_the_raw_word_still_resolves():
    # 0x0842 masks down to APID 0x042 but the payload team ships the raw key.
    result = decode(frame(0x0842, 7.0), {0x0842: "payload_current"})
    assert result.name == "payload_current"


def test_error_names_both_forms_of_the_identifier():
    with pytest.raises(DecodeError, match="0x0512"):
        decode(frame(0x0512, 1.0), {})

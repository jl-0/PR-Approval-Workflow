import pytest

from aurora.dictionary import DictionaryConflict, merge


def test_disjoint_sources_combine():
    assert merge([("bus", {0x42: "v"}), ("payload", {0x512: "t"})]) == {
        0x42: "v",
        0x512: "t",
    }


def test_identical_duplicate_is_allowed():
    assert merge([("a", {0x42: "v"}), ("b", {0x42: "v"})]) == {0x42: "v"}


def test_conflicting_apid_names_both_owners():
    with pytest.raises(DictionaryConflict, match="bus.*payload|payload.*bus"):
        merge([("bus", {0x42: "voltage"}), ("payload", {0x42: "temp"})])

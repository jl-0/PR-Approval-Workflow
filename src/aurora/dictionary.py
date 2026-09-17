"""Assembly of the APID-to-measurand dictionary."""

from __future__ import annotations

from collections.abc import Iterable


class DictionaryConflict(ValueError):
    """Raised when two sources claim the same APID."""


def merge(sources: Iterable[tuple[str, dict[int, str]]]) -> dict[int, str]:
    """Combine per-subsystem dictionaries into one.

    A conflicting APID is an error rather than a last-one-wins overwrite: the
    consequence of getting it wrong is a measurand attributed to the wrong
    subsystem, with nothing anywhere reporting that it happened.
    """
    merged: dict[int, str] = {}
    owners: dict[int, str] = {}
    for owner, entries in sources:
        for apid, name in entries.items():
            if apid in merged and merged[apid] != name:
                raise DictionaryConflict(
                    f"APID {apid:#05x} claimed by {owners[apid]} as "
                    f"{merged[apid]!r} and by {owner} as {name!r}"
                )
            merged[apid] = name
            owners[apid] = owner
    return merged

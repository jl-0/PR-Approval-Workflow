from aurora.api import MeasurandStore
from aurora.decode import Measurand


def test_store_keeps_newest_value():
    store = MeasurandStore()
    store.record(Measurand("bus_voltage", 28.0, 100))
    store.record(Measurand("bus_voltage", 27.5, 200))
    store.record(Measurand("bus_voltage", 99.9, 50))
    assert store.latest("bus_voltage").value == 27.5


def test_names_are_sorted():
    store = MeasurandStore()
    store.record(Measurand("z", 1.0, 1))
    store.record(Measurand("a", 1.0, 1))
    assert store.names() == ["a", "z"]


def test_snapshot_returns_every_current_value():
    store = MeasurandStore()
    store.record(Measurand("a", 1.0, 10))
    store.record(Measurand("b", 2.0, 20))
    snapshot = store.snapshot()
    assert {k: v.value for k, v in snapshot.items()} == {"a": 1.0, "b": 2.0}


def test_snapshot_is_detached_from_later_writes():
    store = MeasurandStore()
    store.record(Measurand("a", 1.0, 10))
    snapshot = store.snapshot()
    store.record(Measurand("a", 9.0, 99))
    assert snapshot["a"].value == 1.0


def test_stale_lists_only_old_measurands():
    store = MeasurandStore()
    store.record(Measurand("fresh", 1.0, 100))
    store.record(Measurand("old", 1.0, 10))
    assert store.stale(now=120, max_age=30) == ["old"]

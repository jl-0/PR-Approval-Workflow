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

# Frame dictionary format

A dictionary maps an APID to the name of the measurand its frames carry.

```python
DICTIONARY = {
    0x042: "bus_voltage",
    0x043: "bus_current",
    0x512: "payload_temp",
}
```

## Keys

A key may be written either as the masked APID (`identifier & 0x07FF`) or as
the raw first header word. Both resolve; the masked form is preferred for new
dictionaries because it is stable across version and type bit changes.

## Registering a measurand

1. Claim an APID with the ground data system team.
2. Add the entry to your subsystem's dictionary module.
3. Add a decode test with a representative frame.

Names are snake_case and stable once published — dashboards, alarm rules, and
archived queries all key on them, so renaming one silently breaks history.

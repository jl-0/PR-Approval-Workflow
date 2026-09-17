# Closing out a pass

Steps for the operator finishing a telemetry pass.

## 1. Record what was discarded

```python
queue.discard_summary()
```

Report the proportion, not just the count. "412 frames discarded" means nothing
without knowing whether 500 or 500,000 were offered.

## 2. Check for stale measurands

```python
store.stale(now=int(time.time()), max_age=300)
```

Anything listed stopped updating during the pass. Note it explicitly — a stale
value on a dashboard is indistinguishable from a current one unless someone says
so.

## 3. Confirm the dictionary merged cleanly

A `DictionaryConflict` during start-up means two subsystems claimed the same
APID. Measurands may be attributed to the wrong subsystem until it is resolved;
do not publish the pass record until it is.

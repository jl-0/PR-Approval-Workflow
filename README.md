# Aurora Telemetry Gateway

A small demo service that ingests spacecraft telemetry frames, decodes them into
named measurands, and serves the latest values over a read-only HTTP API.

> **Note:** this repository is a sandbox for testing a manager sign-off workflow.
> The code is synthetic. The interesting part is [`.github/workflows/release-signoff.yml`](.github/workflows/release-signoff.yml)
> and the process it implements — see [docs/signoff-process.md](docs/signoff-process.md).

## Layout

| Path | Purpose |
| --- | --- |
| `src/aurora/ingest.py` | Frame intake, dedupe, backpressure |
| `src/aurora/decode.py` | Frame → measurand decoding |
| `src/aurora/api.py` | Read-only query surface |
| `src/aurora/config.py` | Runtime configuration |
| `scripts/` | Sign-off report generation |
| `tests/` | Unit tests |

## Development

```bash
python -m pytest tests/
```

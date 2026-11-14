# Development

Use Python 3.14.2 or later and uv. `.python-version` selects 3.14.9; `uv.lock`
pins development dependencies. Production uses Home Assistant's existing aiohttp session.

## Checks

Portable tests run on Windows and Linux:

```console
uv sync --locked
uv run pytest --ignore=tests/ha
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_release.py
uv run python scripts/build_release.py
```

The real Home Assistant suite needs Linux. From this repository in Ubuntu/WSL:

```console
UV_PROJECT_ENVIRONMENT=.venv-linux uv sync --locked --group ha-test
UV_PROJECT_ENVIRONMENT=.venv-linux uv run --locked --group ha-test pytest tests/ha --cov=custom_components.dhl_packstation_monitor.config_flow --cov-branch --cov-report=term-missing --cov-fail-under=100
```

The separate Linux environment preserves the Windows `.venv` and survives WSL clearing
`/tmp`. The `ha-test` group has Linux platform markers. `pytest-homeassistant` and
Home Assistant are both pinned to 2026.11.1; do not install the overlapping older
custom-component test plugin or override dependencies to force compatibility.
The unrelated respx pytest plugin is disabled so HA can initialize its HTTP aliases.

## Boundaries

- Models normalize only needed public fields and contain no HA or network dependencies.
- The API client serializes requests and handles bounded timeouts and rate-limit pauses.
- Flows keep search input in memory and persist verified station metadata only.
- The central entry holds typed runtime data and one coordinator per station.
- Entities are explicitly attached to their config subentry and keep stable unique IDs.
- One entry update listener reloads options and subentry changes. Flow methods do not
  perform a second reload. Unload cancels expiry callbacks and entity subscriptions.

Automated tests use synthetic data and mocked HTTP responses. Live DHL requests and a
temporary Home Assistant smoke test are separate checks, never evidence for automated
coverage. Keep user instructions in the README, technical rationale here and publication
commands in the release procedure. Changelog entries describe product behavior.


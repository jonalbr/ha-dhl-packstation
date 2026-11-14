# Development

Use Python 3.14 and uv. Production uses Home Assistant's existing aiohttp session.

## Checks

Portable tests run on Windows and Linux:

```console
uv sync --locked
uv run pytest --ignore=tests/ha
uv run ruff check .
uv run ruff format --check .
uv run python scripts/build_brand.py --check
uv run python scripts/check_release.py
uv run python scripts/build_release.py
```

The real Home Assistant suite needs Linux. From this repository in Ubuntu/WSL:

```console
UV_PROJECT_ENVIRONMENT=.venv-linux uv sync --locked --group ha-test
UV_PROJECT_ENVIRONMENT=.venv-linux uv run --locked --group ha-test pytest tests --cov=custom_components/dhl_packstation_monitor --cov-branch --cov-report=term-missing --cov-fail-under=100
```

The separate Linux environment preserves the Windows `.venv` and survives WSL clearing
`/tmp`. The `ha-test` group has Linux platform markers. Its Home Assistant and
`pytest-homeassistant` versions are both pinned to 2026.11.1.

The minimum-version suite has a separate project and lockfile in `tests/compat`:

```console
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-minimum-venv" uv sync --locked --project tests/compat
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-minimum-venv" uv run --locked --project tests/compat pytest tests --disable-socket --allow-unix-socket --cov=custom_components/dhl_packstation_monitor --cov-branch --cov-report=term-missing --cov-fail-under=100
```

It pins HA 2026.9.0 and its matching `pytest-homeassistant-custom-component` 0.13.363.
Run the same suite in both environments. Keep the two plugins and their HA dependency
sets separate; no dependency overrides are needed. CI checks both supported endpoints
and the package checker ties the installation minimum to the minimum test project's pin.
The unrelated respx pytest plugin is disabled so HA can initialize its HTTP aliases.
Coverage targets the component directory and gates all integration statements and branches.
Ruff uses its default lint rules and 88-character formatter width; no custom selects
or ignores are configured. CI pins uv 0.13.8 to support the selected Python version.

## Separate live smoke test

The optional `smoke` group installs HA's matching frontend and its standard UI import
dependencies, plus Playwright. These are development packages, not integration requirements.
Run on Linux; a Linux-filesystem environment is faster than one on a Windows-mounted drive:

```console
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-venv" uv sync --locked --group ha-test --group smoke
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-venv" uv run --locked --group ha-test --group smoke playwright install chromium --only-shell
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-venv" uv run --locked --group ha-test --group smoke python scripts/live_smoke.py
```

For the minimum version, sync `tests/compat` with `--group smoke` and run the same
script through that project's environment. Its frontend and optional HA UI packages
are pinned to the versions declared by HA 2026.9.0.

The script starts a fresh HA instance on an unused localhost port with its own generated
account, confirms that instance's HTTP listener through HA's API, and uses the real DHL
service. It checks the location flow, seven entities per station, device links, tile
content for all three variants at desktop and mobile widths in native light and dark
themes, optional capacity editing, home-location clearing, and the more-info dialog.
Manual capacities in its screenshots
are illustrative, not measured locker totals. It stops its server
even when a check fails. Screenshots, logs and the result live under ignored
`.smoke/<HA version>/`;
temporary authentication data must never be committed. It does not contact the user's HA.

Use `tiles-mobile.png` and `tiles-mobile-dark.png` from the same run for the README's
`docs/images/tiles.png` and `docs/images/tiles-dark.png`. HA follows the emulated
browser color preference; the script waits for HA's theme and checks different card
backgrounds before capturing. The README selects the image with `<picture>` sources
and keeps the light image as a fallback.

See [the recorded live check](docs/live-check.md). Automated CI has no live DHL dependency.

## Brand assets

Edit `custom_components/dhl_packstation_monitor/brand/icon.svg`, then run
`uv run python scripts/build_brand.py`. The pinned resvg renderer exports the 256px
and 512px PNGs without a graphics application. CI checks both exports against the
SVG master on Windows and Linux. The locker and magnifying-glass outline use editable
geometric groups; the lens leaves the compartments at their original scale. The DHL
wordmark is embedded as vector paths from
[selfh.st Icons](https://cdn.jsdelivr.net/gh/selfhst/icons/svg/dhl.svg), so rendering
requires no external assets, fonts or network access. The drawing contains no bitmaps.

## Boundaries

- Models normalize only needed public fields and contain no HA or network dependencies.
- The API client serializes requests and handles bounded timeouts and rate-limit pauses.
- Flows keep search input in memory and persist verified station metadata and optional
  display capacities. Home coordinates are resolved only for a submitted home search.
- The central entry holds typed runtime data and one coordinator per station.
- Entities are explicitly attached to their config subentry and keep stable unique IDs.
- One entry update listener reloads options and subentry changes. Flow methods do not
  perform a second reload. Unload cancels expiry callbacks and entity subscriptions.

Automated tests use synthetic data and mocked HTTP responses. Live DHL requests and a
temporary Home Assistant smoke test are separate checks, never evidence for automated
coverage. Keep user instructions in the README, technical rationale here and publication
commands in the release procedure. Changelog entries describe product behavior.


# Development

Use Python 3.14 and uv. Production uses Home Assistant's existing aiohttp session.
The bundled card has no runtime JavaScript dependencies or build step. Its tests use
Node.js 24 or later and run separately from the Python suites. CI uses Node.js 26 LTS.

## Checks

Before release preparation, run `uv run --locked python scripts/check_updates.py`.
It resolves a fresh lockfile in a disposable directory and checks upstream package,
HA/test-plugin/component, CI action, uv, Node LTS and Python patch versions. Exact
HA compatibility constraints are shown as holds. Stale versions or unavailable
upstream metadata block publication; the Release workflow repeats this check.

Portable tests run on Windows and Linux:

```console
uv sync --locked
uv run pytest --ignore=tests/ha
uv run ruff check .
uv run ruff format --check .
uv run python scripts/build_brand.py --check
uv run python scripts/check_release.py
uv run python scripts/build_release.py
node --test tests/frontend/card.test.mjs
```

The real Home Assistant suite needs Linux. From this repository in Ubuntu/WSL:

```console
UV_PROJECT_ENVIRONMENT=.venv-linux uv sync --locked --group ha-test
UV_PROJECT_ENVIRONMENT=.venv-linux uv run --locked --group ha-test pytest tests --cov=custom_components/dhl_packstation_monitor --cov-branch --cov-report=term-missing --cov-fail-under=100
```

The separate Linux environment preserves the Windows `.venv` and survives WSL clearing
`/tmp`. The `ha-test` group has Linux platform markers. Its Home Assistant and
`pytest-homeassistant` versions are both pinned to 2026.11.2.

CI maintains this current HA environment. Minimum-version compatibility was checked
separately with HA 2026.9.0 and its matching legacy test plugin, as recorded in the
[quality assessment](docs/quality-scale.md).

Recheck the minimum after compatibility-sensitive changes using a disposable source
copy and a separate temporary uv project outside the repository. Give that project
HA 2026.9.0, `pytest-homeassistant-custom-component` 0.13.363, `pytest-cov` 7.1.0 and
`resvg-py` 0.5.0, then resolve its own lockfile. Run the same complete suite from the
source copy through that environment with the coverage gate. Keep the current and
legacy test plugins and dependency sets separate without dependency overrides. The
old HA dependency set belongs only to that temporary check; do not commit its project
or lockfile into the maintained development environment.
The unrelated respx pytest plugin is disabled so HA can initialize its HTTP aliases.
Coverage targets the component directory and gates all integration statements and branches.
Ruff uses its default lint rules and 88-character formatter width; no custom selects
or ignores are configured. CI pins uv 0.13.9 to support the selected Python version.

The smoke dependencies match HA 2026.11.2's frontend and component constraints.
Pytest and pytest-asyncio keep the exact versions required by its official test
plugin; newer standalone releases cannot be combined with that plugin. Other
transitive dependencies are refreshed with `uv lock --upgrade`. Python 3.14.10
is the newest 3.14 maintenance release checked for this candidate.

Integration translations ship as complete English/German JSON files. Public
station attributes have labels on every entity; stable state and attribute keys
remain unchanged. The custom card owns its English/German string table, follows
the frontend language and falls back to English. Native controls use HA's own
translations. The card-picker registration accepts a static description, which
remains English.

## Separate live smoke test

The optional `smoke` group installs HA's matching frontend and its standard UI import
dependencies, plus Playwright. These are development packages, not integration requirements.
Run on Linux; a Linux-filesystem environment is faster than one on a Windows-mounted drive:

```console
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-venv" uv sync --locked --group ha-test --group smoke
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-venv" uv run --locked --group ha-test --group smoke playwright install chromium --only-shell
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ha-dhl-packstation-venv" uv run --locked --group ha-test --group smoke python scripts/live_smoke.py
```

For a minimum-version smoke check, use the disposable copy described above and
select the frontend and optional HA UI packages declared by HA 2026.9.0 before
running the same script. Keep its generated lockfile outside the repository.

The script starts a fresh HA instance on an unused localhost port with its own generated
account, confirms that instance's HTTP listener through HA's API, and uses the real DHL
service. It checks the location flow, nine entities per station, device links, card
content for all three display modes at desktop and mobile widths in native light and dark
themes, the optional setup capacity walkthrough, address-format help, the Add station
capacity dialog, optional capacity editing, home-location clearing, and the more-info dialog.
It also creates a separate temporary storage dashboard, adds the bundled card through
the real card picker, configures its display mode, and checks desktop/mobile rendering
in both themes, device-page navigation, and total-count more-info from the icon.
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
- Three independent diagnostic timestamps track source time, poll attempt and poll
  success. A successful parsed response does not imply fresh or complete source data.
- The optional frontend module is served as one static file and registered once at
  integration setup through HA's extra-module API. Entry reloads do not register it
  again or edit dashboard resources. The versioned URL changes with each release.
- The custom card delegates rendering and actions to the native Tile card. Its
  editor filters the integration's devices and localizes English/German. Registry
  platform, device and translation keys resolve sibling entities without relying
  on entity-ID spelling. The diagnostic supplies summaries, the card navigates to
  the device, and the icon opens total-count history. Legacy entity configurations
  are resolved to their device and converted only when the editor is saved.
- One entry update listener reloads options and subentry changes. Flow methods do not
  perform a second reload. Unload cancels expiry callbacks and entity subscriptions.
- Config entry 1.2 migrates the original 60-minute age setting to recommended mode
  by removing its override. Other stored limits are preserved. New entries omit both
  update overrides; both settings are optional, display their recommendations,
  and remove their saved override when cleared. Runtime reads the current
  recommendation when no override exists. The migration runs once, so
  an explicit 60-minute limit saved afterward remains under user control.

Automated tests use synthetic data and mocked HTTP responses. Live DHL requests and a
temporary Home Assistant smoke test are separate checks, never evidence for automated
coverage. Keep user instructions in the README, technical rationale here and publication
commands in the release procedure. Changelog entries describe product behavior.


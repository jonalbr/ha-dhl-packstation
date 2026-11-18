# Internal Bronze assessment

This is an internal assessment against applicable Home Assistant Bronze rules, not
an official tier or certification. Home Assistant designates this integration Custom.

Machine-readable evidence is in the component's quality_scale.yaml. Local brand
assets use the supported custom-integration mechanism. Actions, triggers and conditions
are exempt because the integration provides none. Setup validates every station without
making unrelated stations unavailable when a read fails.

Verification on 2026-11-15 with Python 3.14.10: 69 portable tests pass on Windows;
54 framework tests pass against Home Assistant 2026.11.1 with its matching official
test plugin. Config-flow statement and branch coverage are both 100%. Runtime tests
cover devices, subentry links, stable identities, partial data, independent failures,
expiry without requests, recovery, one reload per change and complete unload.
Additional flow tests cover
home-location defaults, missing coordinates, clearing and replacing the search,
optional capacity editing, validation and removal, and optional per-station totals
during setup and Add station. They also cover skipping totals, cancelling a partial
walkthrough and duplicate stations added during the walkthrough.
Display metadata cannot alter counts.

The combined 123-test Linux run covers all integration modules with 100% statements and
branches (601 statements, 156 branches). CI targets HA 2026.11.2 and enforces this
combined coverage threshold; the portable Windows/Linux jobs remain separate.

The same 123-test suite also passed on the minimum supported HA 2026.9.0 with
its matching legacy test plugin 0.13.363, with 100% statements and branches. The
separate live check also verified that version. Minimum-version rechecks use an
isolated disposable copy, following the Tado integration's approach; the old HA
dependency project and lockfile are not maintained in this repository or CI.

Ten separate Node.js tests cover the bundled card's picker defaults, suggestions,
native Tile updates, optional-name clearing, localization, invalid configuration,
loading failures and configuration changes during asynchronous helper loading.
They also cover device-page and total-history action targets, legacy entity cards,
renamed and unavailable sensors, disabled entities, and preserving layout settings
when changing or clearing the selected device.
Python regressions cover timestamp separation and name/identity preservation;
the HTTP test checks that the bundled asset is served and registered locally.

Verification on 2026-11-18: the 0.3.0 candidate's combined 159-test suite passed against
HA 2026.11.2 with 100% statement and branch coverage (618 statements, 166 branches).
A regression verifies that
70-minute-old data remains usable with the new 75-minute default and expires at
the limit without an HTTP request. Migration regressions verify that the old
60-minute default switches to recommended mode once, other limits stay fixed,
and station and entity identities survive. Options tests cover clearing an
override, preserving unrelated settings and one reload per save.
Translation regressions load public metadata labels through HA for all nine entity
types in English and German, and verify English fallback for an unshipped language.
The same 159 tests and coverage gate passed against the minimum HA 2026.9.0
with its matching legacy test plugin in a disposable source copy and isolated
dependency project. The minimum-version check did not alter maintained dependencies.
The 82 portable tests include offline regressions for outdated release dependencies,
HA compatibility holds, CI tools, Python patches and unavailable upstream metadata.
The online release preflight passed with uv 0.13.9; all versions are current or held
by HA compatibility constraints.

Portable, framework and frontend checks, HACS validation and hassfest run separately in CI.
Release preparation follows the [release procedure](../RELEASING.md). Automated tests
use synthetic data; live checks are separate.
The [separate live check](live-check.md) records real DHL lookup and a temporary HA
instance with two devices, 18 entities and native desktop/mobile tile verification.


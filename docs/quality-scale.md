# Internal Bronze assessment

This is an internal assessment against applicable Home Assistant Bronze rules, not
an official tier or certification. Home Assistant designates this integration Custom.

Machine-readable evidence is in the component's quality_scale.yaml. Local brand
assets use the supported custom-integration mechanism. Actions, triggers and conditions
are exempt because the integration provides none. Setup validates every station without
making unrelated stations unavailable when a read fails.

Verification on 2026-11-15 with Python 3.14.10: 69 portable tests pass on Windows;
43 framework tests pass against Home Assistant 2026.11.1 with its matching official
test plugin. Config-flow
statement and branch coverage are both 100%. Runtime tests cover devices, subentry
links, stable identities, partial data, independent failures, expiry without requests,
recovery, one reload per change and complete unload. Additional flow tests cover
home-location defaults, missing coordinates, clearing and replacing the search,
optional capacity editing, validation and removal. Display metadata cannot alter counts.

The combined Linux run covers all integration modules with 100% statements and
branches (549 statements, 140 branches). CI targets HA 2026.11.1 and enforces this
combined coverage threshold; the portable Windows/Linux jobs remain separate.

The earlier 106-test suite also passed on the minimum supported HA 2026.9.0 with
its matching legacy test plugin 0.13.363, with 100% statements and branches. The
separate live check also verified that version. Minimum-version rechecks use an
isolated disposable copy, following the Tado integration's approach; the old HA
dependency project and lockfile are not maintained in this repository or CI.

Portable and framework checks, HACS validation and hassfest run separately in CI.
No release is authorized. Automated tests use synthetic data; live checks are separate.
The [separate live check](live-check.md) records real DHL lookup and a temporary HA
instance with two devices, 14 entities and native desktop/mobile tile verification.


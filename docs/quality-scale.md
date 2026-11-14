# Internal Bronze assessment

This is an internal assessment against applicable Home Assistant Bronze rules, not
an official tier or certification. Home Assistant designates this integration Custom.

Machine-readable evidence is in the component's quality_scale.yaml. Local brand
assets use the supported custom-integration mechanism. Actions, triggers and conditions
are exempt because the integration provides none. Setup validates every station without
making unrelated stations unavailable when a read fails.

Verification on 2026-11-15 with Python 3.14.10: 63 portable tests pass on Windows;
43 framework tests pass against each of Home Assistant 2026.9.0 and 2026.11.1 with
their matching test plugins in separately locked environments. Config-flow
statement and branch coverage are both 100%. Runtime tests cover devices, subentry
links, stable identities, partial data, independent failures, expiry without requests,
recovery, one reload per change and complete unload. Additional flow tests cover
home-location defaults, missing coordinates, clearing and replacing the search,
optional capacity editing, validation and removal. Display metadata cannot alter counts.

The combined 106-test Linux run on each version covers all integration modules with
100% statements and branches (549 statements, 140 branches). Both framework CI jobs enforce this
combined coverage threshold; the portable Windows/Linux jobs remain separate.

Portable and framework checks, HACS validation and hassfest run separately in CI.
No release is authorized. Automated tests use synthetic data; live checks are separate.
The [separate live check](live-check.md) records real DHL lookup and a temporary HA
instance with two devices, 14 entities and native desktop/mobile tile verification.


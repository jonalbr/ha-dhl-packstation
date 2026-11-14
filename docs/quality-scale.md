# Internal Bronze assessment

This is an internal assessment against applicable Home Assistant Bronze rules, not
an official tier or certification. Home Assistant designates this integration Custom.

Machine-readable evidence is in the component's quality_scale.yaml. Local brand
assets use the supported custom-integration mechanism. Actions, triggers and conditions
are exempt because the integration provides none. Setup validates every station without
making unrelated stations unavailable when a read fails.

Verification on 2026-11-14: 42 portable tests pass on Windows; 29 tests pass against
Home Assistant 2026.11.1 with its matching pytest-homeassistant package. Config-flow
statement and branch coverage are both 100%. Runtime tests cover devices, subentry
links, stable identities, partial data, independent failures, expiry without requests,
recovery, one reload per change and complete unload.

The combined 71-test Linux run covers all integration modules with 100% statements
and branches (490 statements, 118 branches). The framework CI job enforces this
combined coverage threshold; the portable Windows/Linux jobs remain separate.

Portable and framework checks, HACS validation and hassfest run separately in CI.
No release is authorized. Automated tests use synthetic data; live checks are separate.
The [separate live check](live-check.md) records real DHL lookup and a temporary HA
instance with two devices, 14 entities and native desktop/mobile tile verification.


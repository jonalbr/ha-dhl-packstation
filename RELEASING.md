# Release procedure

**Publication is deferred. Do not create a tag or GitHub release for this work.**
The current 0.1.0b1 version is an unreleased development candidate.

## Prepare

1. Keep the manifest and project version identical. Update the Unreleased changelog.
2. Run all development checks, including real HA tests with 100% flow branch coverage.
3. Confirm the exact commit passes portable and HA tests, Ruff, HACS validation and hassfest.
4. Run the release checker and builder. Inspect the deterministic ZIP in `dist/`.
   Its root contains `manifest.json`; extract its files into
   `<config>/custom_components/dhl_packstation_monitor/` for manual installation.
5. Record separate live checks of DHL lookup, temporary HA setup, the tile, reload and removal.

Marketplace installs repository files; the ZIP is a manual-installation artifact.
The local validator checks structure and versions, not upstream catalog eligibility.

## Future publication

After publication is requested, date the changelog, choose the release version and rerun
checks on the final commit. Create its matching tag and GitHub release with the verified
ZIP and concise product notes. Use a prerelease while field validation remains limited.
No workflow automatically publishes tags or releases.

Keep `hacs.json`, local brand icons and Marketplace installation links. Document minimum
HA versions, any migration and restart requirements. Do not claim an official quality tier.


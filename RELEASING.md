# Release procedure

Prepare and merge a release candidate before publishing its matching version tag.
Pushing the tag starts the automated GitHub release workflow described below.

## Prepare

1. Keep the manifest, project and integration version identical. Prepare a dated
   changelog section matching that version.
2. Run all development checks, including the combined HA suite with 100% statement
   and branch coverage of the integration.
3. Confirm the exact commit passes portable and HA tests, Ruff, HACS validation and hassfest.
4. Run the release checker and builder. Inspect the deterministic ZIP in `dist/`.
   Its root contains `manifest.json`; extract its files into
   `<config>/custom_components/dhl_packstation_monitor/` for manual installation.
5. Record separate live checks of DHL lookup, temporary HA setup, the tile, reload and removal.

Marketplace installs repository files; the ZIP is a manual-installation artifact.
The local validator checks structure and versions, not upstream catalog eligibility.

## Automated publication

1. Complete the candidate's live Home Assistant smoke test. Use a manually
   published prerelease if required live validation is incomplete; the automated
   workflow publishes stable releases only.
2. After publication is requested, choose the version, set it in the manifest,
   `pyproject.toml` and `const.py`, run `uv lock`, and prepare a dated
   `## <version> - YYYY-MM-DD` changelog section. Commit and push the version,
   lockfile and notes. Merge the changes to `main` and confirm all jobs in the
   **Validate** workflow succeed for that commit.
3. Update a clean local `main` checkout, then create and push an annotated tag
   matching the manifest and project version:

   ```console
   git switch main
   git pull --ff-only origin main
   git tag -a v0.1.0 -m "Release 0.1.0"
   git push origin v0.1.0
   ```

Pushing a `v*` tag starts the **Release** workflow. It reuses all validation jobs,
then builds the deterministic integration ZIP and publishes a stable GitHub
release with that ZIP and the matching dated section of `CHANGELOG.md`. A tag
that differs from the source version or lacks release notes fails before
publication. Existing releases are never overwritten. Version bumps and live
smoke tests remain manual.

Confirm the workflow succeeds and inspect the published notes and ZIP. Only the
publishing job has repository write permission; it uses GitHub's built-in token,
so no additional release secret is needed.

Keep `hacs.json`, local brand icons and Marketplace installation links. Document minimum
HA versions, any migration and restart requirements. Do not claim an official quality tier.


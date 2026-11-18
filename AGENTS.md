# Repository working conventions

- Keep the README factual and terse, with the logo, purpose and card preview near
  the top. Document the bundled card; do not restore the native Tile YAML examples.
- Prepare release metadata and dated notes in the feature PR. A separate release
  PR is unnecessary. Commit and push requested changes to a feature branch.
- Before every release, run `uv run --locked python scripts/check_updates.py`.
  Resolve stale versions before publishing. The checker compares a fresh lock
  resolution in a disposable copy, leaving the real lockfile untouched.
  The check must cover stable HA and its official test plugin, matching frontend
  and component dependencies, development tools, CI actions, uv, Node LTS, and the
  latest Python patch within the selected minor version. Respect HA's exact pins;
  the checker reports those holds rather than overriding them.
- Run the portable and current/minimum HA tests, lint/format, package checks and
  separate browser smoke test described in DEVELOPMENT.md. Record actual evidence.
- Keep generated environments, caches, credentials and smoke artifacts out of Git.
  Preserve the latest verification evidence when cleaning temporary files.
- Publication requires the user's request. A feature push does not authorize
  merging its PR, tagging a version or publishing a release.

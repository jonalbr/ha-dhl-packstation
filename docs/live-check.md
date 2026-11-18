# Separate live check

Checked on 2026-11-15 with Home Assistant 2026.9.0 and 2026.11.1, each with its
matching pinned frontend (20260826.4 and 20261028.5).
This is separate from the mocked automated tests and is not long-term field validation.

- A disposable instance bound only to localhost; no production Home Assistant changes.
- HA home-coordinate search through the actual DHL endpoint, filtered selection and confirmation.
- Selected public station identifiers: `1-10117407` and `1-10178284`.
- Two devices and 14 registered entities, with seven entities attached to each station.
- All three native tile variants verified against actual attributes at 1280px and 375px.
- Tapping the mobile tile opened the standard data-problem detail view.
- Native search UI selected the home location, cleared it with one click and accepted Hamburg.
- Optional per-size capacities were saved through reconfiguration and shown in the native editor.
- Clearing S in that editor removed only S and retained the other capacities after reload.
- Each instance was stopped after verification; artifacts remain under ignored
  `.smoke/2026.9.0/` and `.smoke/2026.11.1/`.

Observed rows were `S 23 · M 22 · L 10 · XL 4` and `S 9 · M 2 · L 6 · XL 0`.
These are observations at test time, not current availability or reservations.
The first station reported capacity 103 and 59 free compartments. The third tile used
illustrative manual totals 40/30/20/15, not measured capacities. The README preview
shows all three native mobile tiles before clearing the illustrative S total.

On 2026-11-15, all three variants were captured in native HA light and dark themes
from the same live data. HA followed the browser color preference; card backgrounds
were white and RGB 28/28/28 respectively. The README's `<picture>` selected the
matching screenshot in both browser modes. Manual totals remain illustrative.

The setup-flow follow-up on 2026-11-15 was checked with HA 2026.11.1. Initial setup
walked through the optional compartment totals for both selected stations, accepting
empty totals. The native Add station dialogs displayed the address-format example,
the optional totals switch, and an expanded S/M/L/XL editor identifying the station
and showing progress as 1 of 1. That Add station flow was left before saving; the
existing station's Edit station form still loaded and cleared individual totals.
The new dialog screenshots and result are under `.smoke/2026.11.1/`.

The dashboard-card follow-up on 2026-11-15 used HA 2026.9.0 and 2026.11.1 with
their matching frontends. The updated integration created two devices and 18
entities, including the three distinct timestamp diagnostics for each station.
The bundled card loaded without a manually registered dashboard resource and
appeared in the card picker with a native Tile preview. In a separate temporary
storage dashboard, its graphical editor changed the display mode, set and cleared
a custom name, and selected another station before saving. The saved card rendered
at 1280px and 375px in both themes and opened the standard diagnostic details.
Artifacts and per-version result files remain under the ignored `.smoke/` directories.

The 0.2.0 release candidate was rechecked on 2026-11-15 against both matching HA
versions and frontends. Both completed the full setup, optional totals, graphical
card editor, station selection, saved card, native Tile, theme and mobile checks.
The release ZIP was checked for its 0.2.0 manifest and constant, bundled card,
translations, license and direct-install folder structure.

The device-card follow-up on 2026-11-18 used HA 2026.11.1 with its matching
frontend in a disposable instance. The complete live smoke test passed, including
the integration-filtered device picker, selecting another station, saving a
device-based card, and rendering at 1280px and 375px in light and dark themes.
Tapping the icon opened **Free compartments total** for the selected station;
tapping the card opened that station's device page. Setup, capacity editing and
the independent native Tile alternatives also passed. Updated screenshots and
`live-result.json` remain under `.smoke/2026.11.1/`. This follow-up did not repeat
the minimum-version live check.

Reproduce with the commands in the development guide. Publication follows the
[release procedure](../RELEASING.md).

The recommended-age follow-up on 2026-11-18 passed the complete HA 2026.11.1
browser smoke test. It displayed all three bundled-card modes at desktop and
mobile widths in both themes; the README images now show those cards. In the
native integration options dialog, the age field started empty, saved a custom
90-minute limit, cleared it, and remained empty when reopened. Its help text
displayed the 75-minute recommendation. The run also passed the existing device
navigation, total-history, setup and capacity checks. See `recommended-age.png`
and `live-result.json` under `.smoke/2026.11.1/`.

The 0.3.0 candidate passed the full browser check on 2026-11-18. Both update fields
started empty and showed their recommendations (15 and 75 minutes), saved custom
values (30 and 90), and returned to empty recommended mode after clearing and
reopening. See `recommended-settings.png` and `live-result.json` in the same
artifact directory. The candidate's versioned ZIP and dated release notes were
generated successfully; this check did not publish a tag or a GitHub release.

After the dependency refresh, the 0.3.0 candidate passed the same complete browser
check on HA 2026.11.2 with frontend 20261028.6. Device selection, the three display
modes, light/dark and mobile/desktop layouts, both click targets, recommended
settings, setup and capacity editing all passed. Updated artifacts are under
`.smoke/2026.11.2/`. The package was rebuilt with the completed English/German
metadata labels. This was a disposable instance, not a production HA update.

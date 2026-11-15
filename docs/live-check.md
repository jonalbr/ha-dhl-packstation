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

Reproduce with the commands in the development guide. Publication follows the
[release procedure](../RELEASING.md).

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

Reproduce with the commands in the development guide. No tag, release, catalog
submission or production installation was made.

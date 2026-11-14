# Separate live check

Checked on 2026-11-14 with Home Assistant 2026.11.1 and its pinned frontend.
This is separate from the mocked automated tests and is not long-term field validation.

- A disposable instance bound only to localhost; no production Home Assistant changes.
- Address search through the actual DHL endpoint, filtered station selection and confirmation.
- Selected public station identifiers: `1-10117407` and `1-10178284`.
- Two devices and 14 registered entities, with seven entities attached to each station.
- Native tile content verified against the instance's actual attributes at 1280px and 375px.
- Tapping the mobile tile opened the standard data-problem detail view.
- The instance was stopped after verification; its data remain in ignored `.smoke/`.

Observed rows were `S 23 · M 22 · L 10 · XL 4` and `S 9 · M 2 · L 6 · XL 0`.
These are observations at test time, not current availability or reservations.
The README preview shows the first station's native mobile tile.

Reproduce with the commands in the development guide. No tag, release, catalog
submission or production installation was made.

# Changelog

## 0.2.0 - 2026-11-15

- Add a bundled DHL Packstation dashboard card with graphical station selection and
  three display modes. The three existing native Tile examples remain alternatives.
- Distinguish DHL's data timestamp, the last poll attempt, and the last successful
  poll with three timestamp sensors per station. Each station now has nine entities.
- Rename the diagnostic to Problem and clarify the source timestamp's name while
  retaining existing entity identities and custom names.
- Show address-format examples when setting up or adding a station.
- Offer optional per-station S/M/L/XL totals during setup and Add station, with the
  option to finish without them and enter them later under Edit station.
- Explain in setup and Edit station that empty totals mean unknown and 0 means the
  station has no compartments of that size.

After updating, restart Home Assistant and reload your browser to load the bundled
card. In the dashboard editor, choose Add card > By card and search for DHL Packstation.
Existing entity IDs, user names and configured stations are retained. The minimum
supported Home Assistant version remains 2026.9.0.

## 0.1.0 - 2026-11-15

- Support Home Assistant 2026.9.0 and later, tested at the minimum and 2026.11.1.
- Find Packstations by address or postal code and review several locations before setup.
- Manage stations as subentries with individual devices, seven entities and stable identities.
- Configure shared polling and source-age limits; edit station names without changing identity.
- Detect stale, missing, incomplete and failed observations without turning unknown counts into zero.
- Offer Home / Zuhause in search, with one-click clearing for another address.
- Provide three native Tiles: free counts, total / DHL capacity and per-size manual capacities.
- Match README Tile previews to the viewer's light or dark theme.
- Edit optional per-size totals later without changing measurements or availability.
- Include local integration branding for Home Assistant.
- Provide German and English translations and sanitized diagnostics.


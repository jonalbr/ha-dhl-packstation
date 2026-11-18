# Changelog

## 0.3.0 - 2026-11-18

- Choose a Packstation device in the bundled card's graphical editor. Tapping the
  card opens the device page; tapping its icon opens total-count details and history.
  Existing Problem-entity card configurations remain supported.
- Keep descriptive sensor names, including Free compartments total. Problem remains
  a diagnostic and the internal source for the card's unavailable-data summaries.
- Raise the default maximum source age to 75 minutes to accommodate occasional
  hourly DHL updates and the polling interval. Migrate the old 60-minute default
  to recommended mode. Clear the optional age field to follow the recommendation;
  other saved limits stay fixed.
- Make the polling interval clearable too. Both options display their recommendation
  and accept a fixed override; clearing an override restores recommended mode.
- Focus the README on the bundled card, show its preview near the top, and remove
  the separate native Tile YAML examples.
- Translate public station metadata labels in English and German.
- Refresh development dependencies for HA 2026.11.2 and its matching frontend;
  update CI to uv 0.13.9 and Node.js 26 LTS.
- Check upstream versions and HA dependency alignment before publishing releases.

After updating, restart Home Assistant and reload your browser. Existing station
and entity identities, recorded history, and legacy card configurations are retained.
The old 60-minute source-age setting switches to recommended mode automatically;
other saved limits stay fixed. The minimum Home Assistant version remains 2026.9.0.

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


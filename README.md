# DHL Packstation Monitor

<img src="custom_components/dhl_packstation_monitor/brand/icon.svg" width="96" height="96" alt="DHL Packstation Monitor">

> [!NOTE]
> **AI-assisted development:** AI tools helped write the code, tests and documentation.

See the free S, M, L and XL compartments of German DHL Packstations in Home Assistant.
Find stations by address or postal code, review their locations, and add several at once.
No DHL account or API key is required.

This is an independent community integration, not an official DHL product.

## Requirements

- Home Assistant **2026.9.0 or later**. Tested with **2026.9.0** and **2026.11.1**.
- HTTPS access to `www.dhl.de`.
- A Packstation listed by DHL. Some stations provide no live compartment data.

## Installation

[![Open the repository in your Home Assistant Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=jonalbr&repository=ha-dhl-packstation&category=integration)

Use the repository button above to open this integration in Home Assistant
Marketplace, download it, and restart Home Assistant. Continue with [setup](#setup).

<details>
<summary>HACS (Home Assistant <2026.11)</summary>

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/jonalbr/ha-dhl-packstation` with category **Integration**.
3. Download **DHL Packstation Monitor** and restart Home Assistant.
4. Continue with [setup](#setup).

For updates, update through HACS and restart Home Assistant.

</details>

## Setup

1. Open **Settings > Devices & services > Add integration > DHL Packstation Monitor**.
2. Search using one line, for example `10117` or `Georgenstraße 31, 10117 Berlin`
   (street and house number, postal code and city). Alternatively, enter a station's
   postal code and number.
3. Select the stations and check their addresses in the preview. Counts shown as
   `—` are unknown or old. A `⚠` means the location could not be verified: retry or
   deselect it.
4. Optionally select **Enter compartment totals now** to enter the maximum S/M/L/XL
   counts for each selected station in turn. Leave it off to finish immediately.
   Unknown totals can stay empty; you can add or change them later under **Edit station**.
5. Confirm. Each station becomes one device under the central integration entry.

Search selects **Home** when valid home coordinates exist.
Home Assistant stores coordinates, not a street address. Click **X** to clear the
selection and enter any other address or postal code. No home location is selected
when coordinates are missing. DHL receives the chosen location only after submission.

Use **Add station** on that entry to add further stations individually. Existing stations
are excluded from search results. **Edit station** changes the displayed name and
rechecks the same DHL identifier; use Add station for a different location. Renaming
does not change entity identities. Device names explicitly overridden in Home Assistant
remain under your control.

Setup and **Add station** offer four optional compartment totals for S/M/L/XL.
You can also enter them later under **Edit station > Compartment totals**.
DHL supplies no totals per size. You can count compartments on site or from a clear
photo, then enter or change the numbers here at any time. Leave unknown sizes empty;
0 means the station has no compartments of that size. Clearing a field removes its
saved value. These numbers affect only the optional
capacity tile and never replace DHL measurements or change availability checks.

Removing a station stops its polling and removes its entities. It does not remove other
stations. The central entry can remain empty so you can add stations again later.

## Entities

Every station has nine entities:

| Entity | Meaning |
| --- | --- |
| Free S / M / L / XL compartments | Four exact nonnegative counts reported by DHL |
| Free compartments total | Sum, available only when all four sizes are known |
| DHL last updated | DHL's last valid source timestamp, retained after a failed request |
| Last poll attempt | When Home Assistant last attempted to fetch this station |
| Last successful poll | When Home Assistant last received and parsed a response successfully |
| Problem | Diagnostic for failed, missing, stale or incomplete data |

Zero means no free compartment of that size. `Unavailable` does not mean zero.
A missing size affects that size and the total; valid sizes remain usable if fresh.
Counts support Home Assistant history and measurement statistics, not cumulative totals.

The three diagnostic timestamps answer different questions: how old DHL's data is,
when HA last tried to fetch it, and when a fetch last succeeded. A successful poll can
still return stale or incomplete data and leave **Problem** active. A failed poll
updates only the attempt time and retains the previous source and successful-poll times.
Poll times describe the current integration run; they are not restored across restarts.

The diagnostic's `reason` attribute distinguishes `cannot_connect`, `station_not_found`,
`invalid_response`, `rate_limited`, `missing_data`, `missing_timestamp`, `future_timestamp`,
`stale_data` and `missing_compartments`. Device entities also expose the public station
identifier, number, postal code and address.

## Options and updates

Global options apply to every station:

| Option | Default | Range |
| --- | --- | --- |
| Polling interval | 15 minutes | 5–60 whole minutes |
| Maximum source age | 60 minutes | 30–1440 whole minutes, at least the polling interval |

The source timestamp is DHL's observation time, not the time of our HTTP request.
Counts expire at their configured age even between requests. Missing timestamps,
timestamps without a timezone, and timestamps more than five minutes in the future
make counts unavailable. A valid old timestamp remains visible for troubleshooting.

Requests share a client and run sequentially. HTTP 429 pauses requests for at least
15 minutes and honors a longer `Retry-After`, in seconds or HTTP-date form. Other
failures retry on the normal polling schedule. Changing settings reloads the entry once.
One station's failure does not prevent the others from loading.

## Dashboard

### DHL Packstation card

The included **DHL Packstation** card lets you choose a station and display mode in
the graphical editor. It uses Home Assistant's native Tile appearance and supports
all three variants below. As alternatives, below are three native Tile examples as well.

Edit a dashboard, choose **Add card > By card**, and search for **DHL Packstation**.
Select the station and one of the three display modes.

The card is bundled with the integration and loaded locally when HA's frontend is
enabled.

For YAML configuration, see [card.yaml](examples/card.yaml). Its `display_mode` is
`free` (default), `total`, or `capacities`.

### Native Tile alternatives

Three native Tile examples use these attributes:

| Variant | Attribute | Example | File |
| --- | --- | --- | --- |
| Free by size | `compartment_summary` | `S 3 · M 0 · L 2 · XL 1` | [tile.yaml](examples/tile.yaml) |
| Free total / DHL capacity, plus sizes | `compartment_total_summary` | `Σ 6/12 · S 3 · M 0 · L 2 · XL 1` | [tile-total.yaml](examples/tile-total.yaml) |
| Free / manual capacity by size | `compartment_capacity_summary` | `S 3/4 · M 0/0 · L 2/3 · XL 1/5` | [tile-capacities.yaml](examples/tile-capacities.yaml) |

The total sensor exposes these attributes. The diagnostic exposes them even when counts
are unavailable: Home Assistant removes extra attributes from unavailable entities.
Use this diagnostic as the native Tile's entity. These examples work independently
of the DHL card. Replace the example entity ID with your station's actual Problem entity:

```yaml
type: tile
entity: binary_sensor.replace_with_your_station_problem
name: Packstation 407
icon: mdi:package-variant-closed
color: amber
state_content: compartment_summary
tap_action:
  action: more-info
```

Change `state_content` to choose another variant. Unknown sizes appear as `—`; stale or
failed data never populate the summary with old counts. Tapping opens the standard
Home Assistant diagnostic details. Open the individual size or total sensors for history.

The station-wide denominator comes from DHL when present; it is not a sum of your
manual entries. A denominator smaller than the current free count appears as `—`.
The `display_capacity_issues` attribute identifies inconsistent manual entries without
raising a data problem. Manual capacities describe the physical locker and remain
visible when live counts expire. Give long summaries enough dashboard width.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/tiles-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/images/tiles.png">
    <img alt="Three native tiles in a temporary HA instance; manual capacities are illustrative." src="docs/images/tiles.png">
  </picture>
</p>

For a notification, use the desired size sensor in a Home Assistant automation and
check that its state is available. Notifications and parcel-size preferences remain
in your automations; the integration creates no custom actions or triggers.

## Limits and privacy

This uses the **DHL website's undocumented service**. Fields, access restrictions and
URLs can change.

Search text or selected home coordinates are sent to DHL and exist only in the active
setup dialog. Saved settings contain selected public stations, polling options and any
manual display capacities, not the original search address or home coordinates.
DHL sees the requesting IP address. No credentials, personal Postnummer, parcel number,
analytics service or external proxy is used. Downloadable diagnostics omit addresses,
search text and raw vendor responses. Public station identifiers remain in diagnostics.

If counts are unavailable, inspect the data timestamp and diagnostic reason. For a
missing station, verify its postal code in DHL's location finder. For request limits,
wait; repeatedly restarting setup does not improve DHL's availability.

## Removal

Remove affected dashboard cards and automations, then delete the integration entry
under Devices & services. Uninstall its repository in the Marketplace and restart
Home Assistant. Manual installations can remove the component folder after deleting
the entry, then restart. Home Assistant manages previously recorded history separately.

## License
[MIT](LICENSE). This is an independent community integration, not an official DHL product.

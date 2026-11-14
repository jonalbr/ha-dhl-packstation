"""Export a small allowlist rather than raw requests or vendor payloads."""


async def async_get_config_entry_diagnostics(hass, entry):
    return {
        "options": dict(entry.options),
        "stations": [
            {
                "station_id": coordinator.subentry.unique_id,
                "problem": coordinator.problem,
                "last_update_success": coordinator.last_update_success,
                "source_timestamp": (
                    coordinator.last_source_timestamp.isoformat()
                    if coordinator.last_source_timestamp
                    else None
                ),
                "counts": dict(coordinator.snapshot.counts)
                if coordinator.usable
                else None,
            }
            for coordinator in entry.runtime_data.coordinators.values()
        ],
    }

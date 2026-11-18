"""Shared integration identifiers and defaults."""

DOMAIN = "dhl_packstation_monitor"
NAME = "DHL Packstation Monitor"
VERSION = "0.3.0"
CARD_URL = f"/{DOMAIN}/dhl-packstation-card.js"
API_BASE = "https://www.dhl.de/int-postfinder/webservice/rest/v1"
CONF_INTERVAL = "scan_interval_minutes"
CONF_MAX_AGE = "max_age_minutes"
DEFAULT_INTERVAL = 15
DEFAULT_MAX_AGE = 75
CONF_DISPLAY_CAPACITIES = "display_capacities"
SIZES = {
    "s": "freeCompartmentsS",
    "m": "freeCompartmentsM",
    "l": "freeCompartmentsL",
    "xl": "freeCompartmentsXl",
}

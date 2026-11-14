"""Synthetic public station payloads shared by portable and HA tests."""

from datetime import UTC, datetime

import pytest


@pytest.fixture
def payload():
    return {
        "primaryKeyPF": "1-10117407",
        "primaryKeyZipRegion": "407",
        "locationType": "PACKSTATION",
        "zipCode": "10117",
        "city": "Berlin",
        "street": "Georgenstr.",
        "houseNo": "31",
        "locationName": "",
        "geoPosition": {"distance": 51},
        "pfOtherinfos": [{"type": "capacity", "content": "12"}],
        "liveStatus": {
            "freeCompartmentsS": 3,
            "freeCompartmentsM": 0,
            "freeCompartmentsL": 2,
            "freeCompartmentsXl": 1,
            "sourceTimestamp": datetime.now(UTC).isoformat(),
        },
    }

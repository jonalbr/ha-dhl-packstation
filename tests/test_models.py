"""Validate identity, unknown values and source freshness."""

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.dhl_packstation_monitor.models import (
    InvalidResponse,
    Station,
    StationNotFound,
    normalize_capacities,
    normalize_location,
    parse_capacity,
    parse_observation,
    parse_search,
    parse_station,
)


@pytest.mark.parametrize(
    "postal,number",
    [("", "1"), ("1234", "12"), ("abcde", "1"), ("12345", "0"), ("12345", "12345")],
)
def test_invalid_location(postal, number):
    with pytest.raises(ValueError):
        normalize_location(postal, number)


def test_station_metadata(payload):
    station = parse_station(payload)
    assert station.address == "Georgenstr. 31, 10117 Berlin"
    assert station.title == "Packstation 407 · 10117 Berlin"
    assert station.label.endswith("51 m")
    assert "distance_m" not in station.to_data()
    assert Station.from_data(station.to_data()).primary_key == station.primary_key
    assert normalize_location(" 01067 ", "0103") == ("01067", "103")
    payload["geoPosition"] = None
    assert not parse_station(payload).label.endswith("m")


@pytest.mark.parametrize("value", [None, [], "wrong"])
def test_bad_envelope(value):
    with pytest.raises(InvalidResponse):
        parse_station(value)
    with pytest.raises(InvalidResponse):
        parse_search(value)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("locationType", "LETTER_BOX", StationNotFound),
        ("primaryKeyPF", "../path", InvalidResponse),
        ("zipCode", None, InvalidResponse),
        ("primaryKeyZipRegion", "0", InvalidResponse),
    ],
)
def test_bad_station(payload, field, value, error):
    payload[field] = value
    with pytest.raises(error):
        parse_station(payload)


def test_identity_mismatch(payload):
    with pytest.raises(InvalidResponse):
        parse_station(payload, "1-99999123")


def test_search_filter_sort_deduplicate(payload):
    far = deepcopy(payload)
    far["primaryKeyPF"] = "1-10117101"
    far["geoPosition"]["distance"] = 100
    missing = deepcopy(payload)
    missing["primaryKeyPF"] = "1-10117102"
    missing["geoPosition"]["distance"] = True
    result = parse_search({"pfLocations": [far, {}, payload, payload, missing]})
    assert [s.primary_key for s in result] == ["1-10117407", "1-10117101", "1-10117102"]
    with pytest.raises(InvalidResponse):
        parse_search({"pfLocations": None})


@pytest.mark.parametrize("count", [None, True, -1, 1.5, "3"])
def test_unknown_counts_not_zero(payload, count):
    payload["liveStatus"]["freeCompartmentsS"] = count
    observation = parse_observation(payload, payload["primaryKeyPF"])
    assert observation.counts["s"] is None
    assert observation.counts["m"] == 0
    assert (
        observation.problem(datetime.now(UTC), timedelta(hours=1))
        == "missing_compartments"
    )
    assert observation.summary(True) == "S — · M 0 · L 2 · XL 1"


@pytest.mark.parametrize("timestamp", [None, "bad", "2026-11-14T12:00:00", 42])
def test_bad_timestamp(payload, timestamp):
    payload["liveStatus"]["sourceTimestamp"] = timestamp
    observation = parse_observation(payload, payload["primaryKeyPF"])
    assert observation.source_timestamp is None
    assert (
        observation.problem(datetime.now(UTC), timedelta(hours=1))
        == "missing_timestamp"
    )


def test_freshness_boundaries(payload):
    observation = parse_observation(payload, payload["primaryKeyPF"])
    now = observation.source_timestamp
    assert observation.problem(now, timedelta(hours=1)) is None
    assert observation.fresh(now + timedelta(minutes=59), timedelta(hours=1))
    assert (
        observation.problem(now + timedelta(hours=1), timedelta(hours=1))
        == "stale_data"
    )
    assert observation.fresh(now - timedelta(minutes=5), timedelta(hours=1))
    assert (
        observation.problem(now - timedelta(minutes=6), timedelta(hours=1))
        == "future_timestamp"
    )
    assert observation.summary(False) == "S — · M — · L — · XL —"


def test_no_live_data_is_still_station(payload):
    payload.pop("liveStatus")
    observation = parse_observation(payload, payload["primaryKeyPF"])
    assert all(value is None for value in observation.counts.values())
    payload["liveStatus"] = []
    with pytest.raises(InvalidResponse):
        parse_observation(payload, payload["primaryKeyPF"])


def test_optional_display_capacities():
    assert normalize_capacities({"s": 12.0, "m": 0, "xl": None, "other": 99}) == {
        "s": 12,
        "m": 0,
    }
    assert normalize_capacities({}) == {}


@pytest.mark.parametrize(
    "value", [True, "12", -1, 1.5, 1001, float("nan"), float("inf")]
)
def test_invalid_display_capacities(value):
    with pytest.raises(ValueError):
        normalize_capacities({"s": value})


@pytest.mark.parametrize(
    "items,expected",
    [
        (None, None),
        ({}, None),
        ([], None),
        ([None, {"type": "model"}], None),
        ([{"type": "capacity", "content": "103"}], 103),
        ([{"type": "capacity", "content": 103}], 103),
        ([{"type": "capacity", "content": "0"}], None),
        ([{"type": "capacity", "content": "bad"}], None),
        ([{"type": "capacity", "content": True}], None),
        ([{"type": "capacity", "content": 0}], None),
        (
            [
                {"type": "capacity", "content": "103"},
                {"type": "capacity", "content": "103"},
            ],
            103,
        ),
        (
            [
                {"type": "capacity", "content": "103"},
                {"type": "capacity", "content": "104"},
            ],
            None,
        ),
    ],
)
def test_reported_station_capacity(items, expected):
    assert parse_capacity({"pfOtherinfos": items}) == expected


def test_three_display_variants_preserve_observations(payload):
    observation = parse_observation(payload, payload["primaryKeyPF"])
    assert observation.summary(True) == "S 3 · M 0 · L 2 · XL 1"
    assert observation.total_summary(True) == "Σ 6/12 · S 3 · M 0 · L 2 · XL 1"
    assert observation.capacity_summary(True, {"s": 4, "m": 0, "l": 3, "xl": 5}) == (
        "S 3/4 · M 0/0 · L 2/3 · XL 1/5"
    )
    assert observation.capacity_summary(True, {}) == "S 3/— · M 0/— · L 2/— · XL 1/—"
    assert (
        observation.capacity_summary(False, {"s": 4})
        == "S —/4 · M —/— · L —/— · XL —/—"
    )
    assert (
        observation.capacity_summary(True, {"s": 1}) == "S 3/— · M 0/— · L 2/— · XL 1/—"
    )
    assert observation.capacity_issues(True, {"s": 1}) == ["s"]
    assert observation.problem(datetime.now(UTC), timedelta(hours=1)) is None
    assert observation.counts["s"] == 3
    assert (
        replace(observation, total_capacity=5).total_summary(True).startswith("Σ 6/—")
    )
    assert (
        replace(observation, total_capacity=None)
        .total_summary(True)
        .startswith("Σ 6/—")
    )
    partial = replace(observation, counts={**observation.counts, "s": None})
    assert partial.total_summary(True).startswith("Σ —/12")
    assert partial.capacity_issues(True, {"s": 1}) == []
    assert observation.total_summary(False) == "Σ —/12 · S — · M — · L — · XL —"

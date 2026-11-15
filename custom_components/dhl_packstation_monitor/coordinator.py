"""Fetch station data and expire observations without another HTTP request."""

import logging
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_INTERVAL,
    CONF_MAX_AGE,
    DEFAULT_INTERVAL,
    DEFAULT_MAX_AGE,
    DOMAIN,
    SIZES,
)
from .models import Observation, PackstationError, RateLimited, Station

_LOGGER = logging.getLogger(__name__)


class StationCoordinator(DataUpdateCoordinator[Observation]):
    def __init__(self, hass, entry, subentry, client):
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{subentry.unique_id}",
            update_interval=timedelta(
                minutes=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)
            ),
        )
        self.client = client
        self.subentry = subentry
        self.max_age = timedelta(
            minutes=entry.options.get(CONF_MAX_AGE, DEFAULT_MAX_AGE)
        )
        self.snapshot = Observation(
            Station.from_data(dict(subentry.data["station"])),
            dict.fromkeys(SIZES),
            None,
        )
        self.last_source_timestamp = None
        self.last_poll_attempt = None
        self.last_successful_poll = None
        self._cancel_expiry = None
        self.failure_reason = "missing_data"

    @property
    def usable(self):
        return self.last_update_success and self.snapshot.fresh(
            dt_util.utcnow(), self.max_age
        )

    @property
    def problem(self):
        if not self.last_update_success:
            return self.failure_reason
        return self.snapshot.problem(dt_util.utcnow(), self.max_age)

    @callback
    def cancel_expiry(self):
        if self._cancel_expiry is not None:
            self._cancel_expiry()
            self._cancel_expiry = None

    @callback
    def _expire(self, now):
        self._cancel_expiry = None
        self.async_update_listeners()

    async def _async_update_data(self):
        self.last_poll_attempt = dt_util.utcnow()
        try:
            observation = await self.client.station(self.subentry.unique_id)
        except RateLimited as err:
            self.failure_reason = err.code
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=err.code,
                retry_after=err.retry_after,
            ) from err
        except PackstationError as err:
            self.failure_reason = err.code
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key=err.code
            ) from err
        self.last_successful_poll = dt_util.utcnow()
        self.cancel_expiry()
        self.snapshot = observation
        timestamp = observation.source_timestamp
        if timestamp is not None and timestamp <= dt_util.utcnow() + timedelta(
            minutes=5
        ):
            self.last_source_timestamp = timestamp
        if observation.fresh(dt_util.utcnow(), self.max_age):
            self._cancel_expiry = async_track_point_in_utc_time(
                self.hass, self._expire, timestamp + self.max_age
            )
        return observation

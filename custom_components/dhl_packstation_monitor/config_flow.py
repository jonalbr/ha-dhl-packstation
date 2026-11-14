"""Find, preview and manage independently identified Packstations."""

from datetime import UTC, datetime, timedelta
from math import isfinite

import probatio
from homeassistant.config_entries import ConfigFlow, ConfigSubentryFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)
from homeassistant.helpers.translation import async_get_translations

from .api import PackstationClient
from .const import (
    CONF_DISPLAY_CAPACITIES,
    CONF_INTERVAL,
    CONF_MAX_AGE,
    DEFAULT_INTERVAL,
    DEFAULT_MAX_AGE,
    DOMAIN,
    NAME,
)
from .models import Observation, PackstationError, normalize_capacities


class StationSteps:
    """Share location steps between initial setup and a new subentry."""

    _multiple = True

    def __init__(self):
        super().__init__()
        self._candidates = {}
        self._selected = []
        self._observations: dict[str, Observation] = {}
        self._api = None

    def _client(self):
        if self._api is None:
            entry = None if self._multiple else self._get_entry()
            runtime = getattr(entry, "runtime_data", None)
            self._api = (
                runtime.client
                if runtime
                else PackstationClient(async_get_clientsession(self.hass))
            )
        return self._api

    def _existing_keys(self):
        if self._multiple:
            return set()
        return {sub.unique_id for sub in self._get_entry().subentries.values()}

    def _home_coordinates(self):
        latitude, longitude = self.hass.config.latitude, self.hass.config.longitude
        if (
            type(latitude) not in (int, float)
            or type(longitude) not in (int, float)
            or not isfinite(latitude)
            or not isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
            or (latitude, longitude) == (0, 0)
        ):
            return None
        return f"{latitude:.6f},{longitude:.6f}"

    async def async_step_search(self, user_input=None):
        errors = {}
        home_coordinates = self._home_coordinates()
        translations = await async_get_translations(
            self.hass, self.hass.config.language, "selector", {DOMAIN}
        )
        # The native custom-value picker renders the selected value verbatim.
        home_label = translations[
            f"component.{DOMAIN}.selector.search_location.options.home"
        ]
        if user_input is not None:
            address = user_input.get("address", "").strip()
            if address == home_label:
                address = home_coordinates or ""
            if not address or len(address) > 300:
                errors["base"] = "invalid_address"
            else:
                try:
                    found = await self._client().search(address)
                except PackstationError as err:
                    errors["base"] = err.code
                else:
                    existing = self._existing_keys()
                    self._candidates = {
                        station.primary_key: station
                        for station in found
                        if station.primary_key not in existing
                    }
                    if self._candidates:
                        return await self.async_step_select()
                    errors["base"] = "no_stations"
        return self.async_show_form(
            step_id="search",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Optional("address"): SelectSelector(
                            SelectSelectorConfig(
                                options=[home_label] if home_coordinates else [],
                                custom_value=True,
                            )
                        ),
                    }
                ),
                user_input
                if user_input is not None
                else ({"address": home_label} if home_coordinates else {}),
            ),
        )

    async def async_step_direct(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                result = await self._client().resolve(
                    user_input["postal_code"], user_input["station_number"]
                )
            except ValueError:
                errors["base"] = "invalid_location"
            except PackstationError as err:
                errors["base"] = err.code
            else:
                key = result.station.primary_key
                if key in self._existing_keys():
                    errors["base"] = "already_configured"
                else:
                    self._candidates = {key: result.station}
                    self._selected = [key]
                    self._observations = {key: result}
                    return await self.async_step_confirm()
        return self.async_show_form(
            step_id="direct",
            errors=errors,
            data_schema=probatio.Schema(
                {
                    probatio.Required("postal_code"): TextSelector(),
                    probatio.Required("station_number"): TextSelector(),
                }
            ),
        )

    def _selection_schema(self, keys, *, preview=False):
        options = []
        for key in keys:
            label = self._candidates[key].label
            if preview:
                observation = self._observations.get(key)
                label += " | " + (
                    observation.summary(
                        observation.fresh(
                            datetime.now(UTC), timedelta(minutes=DEFAULT_MAX_AGE)
                        )
                    )
                    if observation
                    else "⚠"
                )
            options.append({"value": key, "label": label})
        default = (
            self._selected
            if self._multiple
            else self._selected[0]
            if self._selected
            else None
        )
        field = (
            probatio.Required("stations", default=default)
            if default
            else probatio.Required("stations")
        )
        return probatio.Schema(
            {
                field: SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=self._multiple,
                    )
                )
            }
        )

    def _read_selection(self, user_input):
        selected = user_input["stations"]
        if not self._multiple:
            selected = [selected]
        if not selected or any(key not in self._candidates for key in selected):
            return False
        self._selected = list(dict.fromkeys(selected))
        return True

    async def _load_selected(self):
        failed = False
        for key in self._selected:
            try:
                self._observations[key] = await self._client().station(key)
            except PackstationError:
                self._observations.pop(key, None)
                failed = True
        return failed

    async def async_step_select(self, user_input=None):
        errors = {}
        if user_input is not None:
            if self._read_selection(user_input):
                await self._load_selected()
                return await self.async_step_confirm()
            errors["base"] = "no_selection"
        return self.async_show_form(
            step_id="select",
            errors=errors,
            data_schema=self._selection_schema(self._candidates),
        )

    async def async_step_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            if not self._read_selection(user_input):
                errors["base"] = "no_selection"
            elif any(key in self._existing_keys() for key in self._selected):
                errors["base"] = "already_configured"
            elif await self._load_selected():
                errors["base"] = "validation_failed"
            else:
                subentries = [
                    {
                        "subentry_type": "station",
                        "unique_id": key,
                        "title": self._observations[key].station.title,
                        "data": {"station": self._observations[key].station.to_data()},
                    }
                    for key in self._selected
                ]
                if self._multiple:
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=NAME,
                        data={},
                        subentries=subentries,
                        options={
                            CONF_INTERVAL: DEFAULT_INTERVAL,
                            CONF_MAX_AGE: DEFAULT_MAX_AGE,
                        },
                    )
                sub = subentries[0]
                return self.async_create_entry(
                    title=sub["title"],
                    data=sub["data"],
                    unique_id=sub["unique_id"],
                )
        elif any(key not in self._observations for key in self._selected):
            errors["base"] = "validation_failed"
        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            data_schema=self._selection_schema(self._selected, preview=True),
        )


class MonitorConfigFlow(StationSteps, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_show_menu(step_id="user", menu_options=["search", "direct"])

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry):
        return {"station": StationSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MonitorOptionsFlow()


class StationSubentryFlow(StationSteps, ConfigSubentryFlow):
    _multiple = False

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(step_id="user", menu_options=["search", "direct"])

    async def async_step_reconfigure(self, user_input=None):
        subentry = self._get_reconfigure_subentry()
        errors = {}
        if user_input is not None:
            try:
                capacities = normalize_capacities(
                    user_input.get(CONF_DISPLAY_CAPACITIES, {})
                )
                observation = await self._client().station(subentry.unique_id)
            except ValueError:
                errors["base"] = "invalid_capacities"
            except PackstationError as err:
                errors["base"] = err.code
            else:
                name = user_input["name"].strip() or observation.station.title
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=name,
                    data={
                        "station": observation.station.to_data(),
                        CONF_DISPLAY_CAPACITIES: capacities,
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            errors=errors,
            description_placeholders={"station": subentry.title},
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(
                            "name", default=subentry.title
                        ): TextSelector(),
                        probatio.Optional(CONF_DISPLAY_CAPACITIES): section(
                            probatio.Schema(
                                {
                                    probatio.Optional(size): NumberSelector(
                                        NumberSelectorConfig(
                                            min=0,
                                            max=1000,
                                            step=1,
                                            mode=NumberSelectorMode.BOX,
                                        )
                                    )
                                    for size in ("s", "m", "l", "xl")
                                }
                            ),
                            {"collapsed": True},
                        ),
                    }
                ),
                user_input
                if user_input is not None
                else {
                    CONF_DISPLAY_CAPACITIES: dict(
                        subentry.data.get(CONF_DISPLAY_CAPACITIES, {})
                    ),
                },
            ),
        )


class MonitorOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            interval, max_age = user_input[CONF_INTERVAL], user_input[CONF_MAX_AGE]
            if (
                interval != int(interval)
                or max_age != int(max_age)
                or not 5 <= interval <= 60
                or not 30 <= max_age <= 1440
                or max_age < interval
            ):
                errors["base"] = "invalid_options"
            else:
                return self.async_create_entry(
                    data={
                        CONF_INTERVAL: int(interval),
                        CONF_MAX_AGE: int(max_age),
                    }
                )
        fields = {}
        for key, default, minimum, maximum in (
            (CONF_INTERVAL, DEFAULT_INTERVAL, 5, 60),
            (CONF_MAX_AGE, DEFAULT_MAX_AGE, 30, 1440),
        ):
            fields[
                probatio.Required(
                    key, default=self.config_entry.options.get(key, default)
                )
            ] = NumberSelector(
                NumberSelectorConfig(
                    min=minimum,
                    max=maximum,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            )
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=probatio.Schema(fields),
        )

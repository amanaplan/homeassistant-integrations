"""Support for SmartCocoon fans."""
from __future__ import annotations

import logging

from homeassistant.components.fan import (
    ENTITY_ID_FORMAT,
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id

from .const import (
    DOMAIN,
)

from . import SmartCocoonController
from .model import FanExtraAttributes

from pysmartcocoon.manager import SmartCocoonManager
from pysmartcocoon.fan import Fan as PySmartCocoonFan

_LOGGER = logging.getLogger(__name__)

ATTR_ROOM_NAME = "room_name"

SC_PRESET_MODE_AUTO = "auto"
SC_PRESET_MODE_ECO = "eco"

SC_PRESET_MODES = [ SC_PRESET_MODE_AUTO, SC_PRESET_MODE_ECO ]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Initialize sensor platform from config entry."""

    _LOGGER.debug("Starting async_setup_entry")

    smartcocoon: SmartCocoonController = hass.data[DOMAIN][config_entry.entry_id]
    scmanager: SmartCocoonManager = smartcocoon.scmanager

    fans = []

    for fan_id in scmanager.fans:
        _LOGGER.debug(f"Adding Entity for fan_id: {fan_id}")
        fans.append(SmartCocoonFan(hass, smartcocoon, fan_id, config_entry))

    async_add_entities(fans)

    _LOGGER.debug("Completed async_setup_entry")


class SmartCocoonFan(FanEntity):
    """A SmartCocoon fan entity."""

    def __init__(
        self, hass: HomeAssistant,
        smartcocoon: SmartCocoonController,
        fan_id: str,
        config_entry: ConfigEntry):

        """Initialize the SmartCocoon entity."""

        self._fan_id = fan_id
        self._scmanager = smartcocoon.scmanager
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{self._scmanager.fans[self._fan_id].room_name}_{self._fan_id}",
            hass=hass
        )

        # The fan can be updated direcly by the SmartCocoon app, the pysmartcooon api handles this
        self._scmanager.fans[self._fan_id]._async_update_fan_callback = self.async_update_fan_callback

        _LOGGER.debug("Initialized fan_id: %s", self._fan_id)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._scmanager.fans[self._fan_id].connected

    @property
    def device_info(self) -> DeviceInfo:
        """Return info for device registry."""

        _LOGGER.debug("device_info: fan_id: %s, sw_version: %s",
            self._fan_id,
            self._scmanager.fans[self._fan_id].firmware_version)

        return {
            "identifiers": {(DOMAIN, f"smartcocoon_fan_{self._fan_id}")},
            "name": f"{self._scmanager.fans[self._fan_id].room_name}:{self._fan_id}",
            "model": "Smart Vent",
            "sw_version": self._scmanager.fans[self._fan_id].firmware_version,
            "manufacturer": "SmartCocoon",
        }

    @property
    def extra_state_attributes(self) -> FanExtraAttributes:
        """Return the device specific state attributes."""
        attrs: FanExtraAttributes = {
            ATTR_ROOM_NAME: self._scmanager.fans[self._fan_id].room_name
        }

        return attrs

    @property
    def is_connected(self):
        """Return whether the mock bridge is connected."""
        return self._scmanager.fans[self._fan_id].connected

    @property
    def is_on(self):
        """Return true if the fan is on."""
        return self._scmanager.fans[self._fan_id].fan_on

    @property
    def fan_id(self):
        """Return the physical ID of the fan."""
        return self._fan_id

    @property
    def name(self) -> str:
        """Get entity name."""
        return f"SmartCocoon Fan - {self._scmanager.fans[self._fan_id].room_name}:{self._fan_id}"

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        return self._scmanager.fans[self._fan_id].power / 100

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""
        return self._scmanager.fans[self._fan_id].mode

    #@property
    #def preset_modes(self):
    #    """List of available preset modes."""
    #    return SC_PRESET_MODES

    @property
    def should_poll(self):
        """No polling needed, updates come from MQTT."""
        return False

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return 100

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this fan."""
        return "_".join(
            [DOMAIN, "fan", self._fan_id]
        ).lower()

    async def async_update_fan_callback(self) -> None:
        """Callback to receive updates from the SmartCocoon mobile app directly."""
        _LOGGER.debug("Fan ID: %s - Received update callback",
            self.fan_id
        )
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self._scmanager.async_set_fan_speed(self._fan_id, percentage)
        self._power = percentage * 100
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in SC_PRESET_MODES:
            raise ValueError(
                "{preset_mode} is not a valid preset_mode: {SC_PRESET_MODES}"
            )

        if preset_mode == SC_PRESET_MODE_AUTO:
            await self._scmanager.async_fan_auto(self._fan_id)
        elif preset_mode == SC_PRESET_MODE_ECO:
            await self._scmanager.async_fan_eco(self._fan_id)
        else:
            raise ValueError(f"Unsupported preset mode {preset_mode}")

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        await self._scmanager.async_fan_turn_off(self._fan_id)
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the entity."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return

        if percentage is not None:
            await self.async_set_percentage(percentage)

        await self._scmanager.async_fan_turn_on(self._fan_id)
        self.async_write_ha_state()

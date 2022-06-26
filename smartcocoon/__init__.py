"""The SmartCocoon integration."""
from __future__ import annotations

import logging

from datetime import timedelta

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed
from .const import (
    DOMAIN,
)

from pysmartcocoon.manager import SmartCocoonManager
from pysmartcocoon.fan import Fan as PySmartCocoonFan
from pysmartcocoon.errors import UnauthorizedError, SmartCocoonError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["fan"]

class SmartCocoonController:
    """SmartCocoon main class."""

    def __init__(self, username, password, hass):
        """Initialize."""
        self._username = username
        self._password = password
        self._scmanager: SmartCocoonManager = None
        self._hass = hass
        self._session = None


    @property
    def scmanager(self):
        """Return the SmartCocoonManager object."""
        return self._scmanager


    async def async_start(self) -> bool:
        """Start the SmartCocoon Manager."""

        _LOGGER.debug("Starting SmartCocoon services")

        self._session = async_get_clientsession(self._hass)
        self._scmanager = SmartCocoonManager(
            self._session
        )

        try:
            await self._scmanager.async_start_services(
                username = self._username,
                password = self._password,
                use_mqtt = False
            )
        except (
            UnauthorizedError,
        ) as exc:
            raise ConfigEntryAuthFailed() from exc

        _LOGGER.debug("SmartCocoon services started successfully")

        _LOGGER.debug(f"scmanager.locations: {len(self._scmanager.locations)}")
        _LOGGER.debug(f"scmanager.thermostats: {len(self._scmanager.thermostats)}")
        _LOGGER.debug(f"scmanager.rooms: {len(self._scmanager.rooms)}")
        _LOGGER.debug(f"scmanager.fans: {len(self._scmanager.fans)}")

        return True

    async def async_stop(self) -> bool:
        """Stop the SmartCocoon Manager."""

        _LOGGER.debug("Stopping SmartCocoon services")

        await self._scmanager.async_stop_services()
        return True

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry
) -> bool:
    """Set up SmartCocoon from a config entry."""

    smartcocoon = SmartCocoonController(
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        hass,
    )

    await smartcocoon.async_start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = smartcocoon

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True

async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry
) -> bool:
    """Unload a config entry."""

    smartcocoon: SmartCocoonController = hass.data[DOMAIN][config_entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    await smartcocoon.async_stop()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok

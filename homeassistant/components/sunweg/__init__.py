"""The Sun WEG inverter sensor integration."""
import asyncio
import datetime
import logging

from sunweg.api import APIHelper, LoginError, SunWegApiError
from sunweg.plant import Plant

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PLANT_ID, DEFAULT_PLANT_ID, DOMAIN, PLATFORMS, DeviceType

SCAN_INTERVAL = datetime.timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Load the saved entities."""
    api = APIHelper(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    if not await hass.async_add_executor_job(api.authenticate):
        _LOGGER.error("Username or Password may be incorrect!")
        return False
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, entry.data[CONF_PLANT_ID], entry.data[CONF_NAME]
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class SunWEGDataUpdateCoordinator(DataUpdateCoordinator[Plant]):
    """SunWEG Data Update Coordinator coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: APIHelper, plant_id: int, plant_name: str
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="SunWEG sensor",
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.plant_id = plant_id
        self.plant_name = plant_name
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, str(plant_id))},
            manufacturer="SunWEG",
            name=self.plant_name,
        )

    async def _async_update_data(self) -> Plant:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(10):
                if self.plant_id == DEFAULT_PLANT_ID:
                    plant = self.api.listPlants()[0]
                    self.plant_id = plant.id
                    self.plant_name = plant.name
                else:
                    plant = self.api.plant(self.plant_id)
                for inverter in plant.inverters:
                    self.api.complete_inverter(inverter)
                return plant
        except LoginError as err:
            # raise ConfigEntryAuthFailed from err
            raise UpdateFailed("LoginError") from err
        except SunWegApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def get_api_value(
        self,
        variable: str,
        device_type: DeviceType,
        inverter_id: int = 0,
        deep_name: str | None = None,
    ) -> StateType | datetime.datetime | None:
        """Retrieve from a Plant the desired variable value."""
        if device_type == DeviceType.TOTAL:
            return getattr(self.data, variable)

        inverter_list = [i for i in self.data.inverters if i.id == inverter_id]
        if len(inverter_list) == 0:
            return None
        inverter = inverter_list[0]

        if device_type == DeviceType.INVERTER:
            return getattr(inverter, variable)
        if device_type == DeviceType.PHASE:
            for phase in inverter.phases:
                if phase.name == deep_name:
                    return getattr(phase, variable)
        elif device_type == DeviceType.STRING:
            for mppt in inverter.mppts:
                for string in mppt.strings:
                    if string.name == deep_name:
                        return getattr(string, variable)
        return None

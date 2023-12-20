"""Read status of SunWEG inverters."""
from __future__ import annotations

import datetime
import logging
from types import MappingProxyType
from typing import Any

from sunweg.device import Inverter
from sunweg.plant import Plant

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SunWEGDataUpdateCoordinator
from .const import DOMAIN, DeviceType
from .sensor_types.inverter import INVERTER_SENSOR_TYPES
from .sensor_types.phase import PHASE_SENSOR_TYPES
from .sensor_types.sensor_entity_description import SunWEGSensorEntityDescription
from .sensor_types.string import STRING_SENSOR_TYPES
from .sensor_types.total import TOTAL_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


def get_device_list(plant: Plant, config: MappingProxyType[str, Any]) -> list[Inverter]:
    """Retrieve the device list for the selected plant."""
    devices: list[Inverter] = []
    # Get a list of devices for specified plant to add sensors for.
    for inverter in plant.inverters:
        devices.append(inverter)
    return devices


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SunWEG sensor."""
    name = config_entry.data[CONF_NAME]

    coordinator: SunWEGDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_config_entry_first_refresh()

    devices = await hass.async_add_executor_job(
        get_device_list, coordinator.data, config_entry.data
    )

    entities = [
        SunWEGInverter(
            coordinator=coordinator,
            name=f"{name} Total",
            unique_id=f"{coordinator.plant_id}-{description.key}",
            description=description,
            device_type=DeviceType.TOTAL,
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device in the specified plant.
    entities.extend(
        [
            SunWEGInverter(
                coordinator=coordinator,
                name=f"{device.name}",
                unique_id=f"{device.sn}-{description.key}",
                description=description,
                device_type=DeviceType.INVERTER,
                inverter_id=device.id,
            )
            for device in devices
            for description in INVERTER_SENSOR_TYPES
        ]
    )

    entities.extend(
        [
            SunWEGInverter(
                coordinator=coordinator,
                name=f"{device.name} {phase.name}",
                unique_id=f"{device.sn}-{phase.name}-{description.key}",
                description=description,
                inverter_id=device.id,
                device_type=DeviceType.PHASE,
                deep_name=phase.name,
            )
            for device in devices
            for phase in device.phases
            for description in PHASE_SENSOR_TYPES
        ]
    )

    entities.extend(
        [
            SunWEGInverter(
                coordinator=coordinator,
                name=f"{device.name} {string.name}",
                unique_id=f"{device.sn}-{string.name}-{description.key}",
                description=description,
                inverter_id=device.id,
                device_type=DeviceType.STRING,
                deep_name=string.name,
            )
            for device in devices
            for mppt in device.mppts
            for string in mppt.strings
            for description in STRING_SENSOR_TYPES
        ]
    )

    async_add_entities(entities, True)


class SunWEGInverter(CoordinatorEntity[SunWEGDataUpdateCoordinator], SensorEntity):
    """Representation of a SunWEG Sensor."""

    entity_description: SunWEGSensorEntityDescription

    def __init__(
        self,
        name: str,
        unique_id: str,
        coordinator: SunWEGDataUpdateCoordinator,
        description: SunWEGSensorEntityDescription,
        device_type: DeviceType,
        inverter_id: int = 0,
        deep_name: str | None = None,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device_type = device_type
        self.inverter_id = inverter_id
        self.deep_name = deep_name

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id
        self._attr_icon = (
            description.icon if description.icon is not None else "mdi:solar-power"
        )

        self._attr_device_info = coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        previous_value = self.native_value
        value: StateType | datetime.datetime = self.coordinator.get_api_value(
            self.entity_description.api_variable_key,
            self.device_type,
            self.inverter_id,
            self.deep_name,
        )
        previous_unit_of_measurement: str | None = self.native_unit_of_measurement
        unit_of_measurement: str | None = str(
            self.coordinator.get_api_value(
                self.entity_description.api_variable_unit,
                self.device_type,
                self.inverter_id,
                self.deep_name,
            )
            if self.entity_description.api_variable_unit is not None
            else self.native_unit_of_measurement
        )

        # Never resets validation
        if (
            self.entity_description.never_resets
            and isinstance(value, float)
            and isinstance(previous_value, float)
            and (value is None or value == 0)
        ):
            value = previous_value
            unit_of_measurement = previous_unit_of_measurement

        self._attr_native_value = value
        self._attr_native_unit_of_measurement = unit_of_measurement
        self.async_write_ha_state()

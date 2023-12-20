"""Tests for the Sun WEG init."""

import json
from unittest.mock import MagicMock, patch

from sunweg.api import APIHelper, LoginError, SunWegApiError

from homeassistant.components.sunweg import SunWEGDataUpdateCoordinator
from homeassistant.components.sunweg.const import DOMAIN, DeviceType
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import SUNWEG_MOCK_ENTRY


async def test_methods(hass: HomeAssistant, plant_fixture, inverter_fixture) -> None:
    """Test methods."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper, "listPlants", return_value=[plant_fixture]
    ), patch.object(APIHelper, "plant", return_value=plant_fixture), patch.object(
        APIHelper, "inverter", return_value=inverter_fixture
    ), patch.object(APIHelper, "complete_inverter"):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(mock_entry.entry_id)


async def test_setup_wrongpass(hass: HomeAssistant) -> None:
    """Test setup with wrong pass."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch.object(APIHelper, "authenticate", return_value=False):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()


async def test_setup_auth_expired(hass: HomeAssistant) -> None:
    """Test setup with auth expired."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper, "listPlants", side_effect=LoginError("Auth expired")
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()


async def test_setup_error_500(hass: HomeAssistant) -> None:
    """Test setup with wrong pass."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper, "listPlants", side_effect=SunWegApiError("Error 500")
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        await hass.async_block_till_done()


async def test_sunwegdata_update_exception(hass: HomeAssistant) -> None:
    """Test SunWEGData exception on update."""
    api = MagicMock()
    api.plant = MagicMock(side_effect=json.decoder.JSONDecodeError("Message", "Doc", 1))
    data = SunWEGDataUpdateCoordinator(hass, api, 123456, "name")
    await data.async_refresh()
    assert data.data is None


async def test_sunwegdata_update_success(hass: HomeAssistant, plant_fixture) -> None:
    """Test SunWEGData success on update."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    data = SunWEGDataUpdateCoordinator(hass, api, plant_fixture.id, "name")
    await data.async_refresh()
    assert data.data.id == plant_fixture.id
    assert data.data.name == plant_fixture.name
    assert data.data.kwh_per_kwp == plant_fixture.kwh_per_kwp
    assert data.data.last_update == plant_fixture.last_update
    assert data.data.performance_rate == plant_fixture.performance_rate
    assert data.data.saving == plant_fixture.saving
    assert len(data.data.inverters) == 1


async def test_sunwegdata_get_api_value_none(
    hass: HomeAssistant, plant_fixture
) -> None:
    """Test SunWEGDataUpdateCoordinator none return on get_api_value."""
    api = MagicMock()
    data = SunWEGDataUpdateCoordinator(hass, api, plant_fixture.id, "name")
    data.data = plant_fixture
    assert data.get_api_value("variable", DeviceType.INVERTER, 0, "deep_name") is None
    assert data.get_api_value("variable", DeviceType.STRING, 21255, "deep_name") is None


async def test_sunwegdata_get_api_value_total(
    hass: HomeAssistant, plant_fixture
) -> None:
    """Test SunWEGDataUpdateCoordinator value return for total attribute."""
    api = MagicMock()
    data = SunWEGDataUpdateCoordinator(hass, api, plant_fixture.id, "name")
    data.data = plant_fixture
    assert (
        data.get_api_value("total_power", DeviceType.TOTAL) == plant_fixture.total_power
    )
    assert (
        data.get_api_value("total_energy", DeviceType.TOTAL)
        == plant_fixture.total_energy
    )
    assert (
        data.get_api_value("today_energy_metric", DeviceType.TOTAL)
        == plant_fixture.today_energy_metric
    )
    assert (
        data.get_api_value("total_carbon_saving", DeviceType.TOTAL)
        == plant_fixture.total_carbon_saving
    )

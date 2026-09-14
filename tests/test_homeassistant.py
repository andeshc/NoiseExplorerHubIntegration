"""Exercise real HA classes with only the vendor network boundary simulated."""

from importlib import import_module
from types import MappingProxyType
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from custom_components.noise_explorer.client.api import AuthenticationError, ConnectionError
from custom_components.noise_explorer.const import NUMBERS, PLATFORMS, SELECTS, SWITCHES
from custom_components.noise_explorer.coordinator import NoiseCoordinator
from custom_components.noise_explorer.diagnostics import async_get_config_entry_diagnostics
from custom_components.noise_explorer.services import validate_setting


@pytest.mark.parametrize(
    ("rc", "expected"),
    [(-101, "wrong_password"), (-103, "unknown_email"), (-123, "login_throttled"),
     (-127, "account_locked"), (-14, "invalid_session"), (-400, "server_redirect"),
     (-999, "invalid_auth")],
)
async def test_login_form_explains_server_error(coordinator, monkeypatch, rc, expected):
    from custom_components.noise_explorer import config_flow

    client = AsyncMock()
    client.connect.side_effect = AuthenticationError("Sign-in rejected", rc=rc)
    monkeypatch.setattr(config_flow, "NoiseClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(config_flow, "async_get_clientsession", lambda hass: None)
    flow = config_flow.NoiseConfigFlow()
    flow.hass = coordinator.hass
    result = await flow.async_step_user({"email": "test@example.test", "password": "test"})
    assert result["errors"] == {"base": expected}
    assert result["description_placeholders"] == {"error_code": str(rc)}
    client.close.assert_awaited_once()


@pytest.fixture
async def coordinator(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    await hass.config.async_set_time_zone("Asia/Kolkata")
    entry = ConfigEntry(
        domain="noise_explorer",
        data={"email": "private-email", "password": "private-password"},
        options={},
        unique_id="private-account",
        title="Noise",
        source="user",
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
        state=ConfigEntryState.LOADED,
    )
    client = AsyncMock()
    client.connected = True
    client.read_offline.return_value = 0
    client.discover.return_value = [
        {"EID": "watch1", "GID": "group1", "NickName": "Private child", "VersionCur": "v1"}
    ]
    client.read_settings.return_value = {
        "battery_level": "20260914123000123_84",
        "cur_steps": "20260914_1200",
        "signal_level": "20260914123000123_20",
        "status": "0",
        "net_stat": "4G",
        "AlarmClockList": "[]",
        "SilenceList": "[]",
        "SleepList": "[]",
        **dict.fromkeys(SWITCHES, "1"),
        **{key: next(iter(options.values())) for key, (_, options) in SELECTS.items()},
        **dict.fromkeys(NUMBERS, "8000"),
    }
    result = NoiseCoordinator(hass, entry, client)
    entry.runtime_data = result
    result.data = await result._async_update_data()
    yield result
    await result.async_shutdown()
    await hass.async_stop(force=True)


async def all_entities(coordinator):
    entities = []
    for platform in PLATFORMS:
        module = import_module(f"custom_components.noise_explorer.{platform}")
        await module.async_setup_entry(coordinator.hass, coordinator.entry, entities.extend)
    return entities


async def test_all_platforms_create_real_entities_and_valid_states(coordinator):
    entities = await all_entities(coordinator)
    assert len(entities) == 51
    assert len({(type(e), e.unique_id) for e in entities}) == 51
    by_key = {e.key: e for e in entities}
    assert by_key["battery_level"].native_value == 84
    assert by_key["cur_steps"].native_value == 1200
    assert by_key["status"].is_on is False
    assert by_key["watch_online"].is_on is True
    assert by_key["VersionCur"].native_value == "v1"
    assert by_key["auto_answer"].current_option == "Off"
    assert by_key["low_battery"].is_on is False
    assert by_key["location"].available is False
    assert by_key["battery_level"].device_info["manufacturer"] == "Noise"
    coordinator.watches["watch1"].settings["battery_level"] = None
    assert by_key["battery_level"].native_value is None
    assert by_key["low_battery"].is_on is None


async def test_dynamic_controls_only_appear_after_supported_field(coordinator):
    coordinator.watches["watch1"].settings.pop("keep_wifi_connect")
    entities = []
    module = import_module("custom_components.noise_explorer.switch")
    await module.async_setup_entry(coordinator.hass, coordinator.entry, entities.extend)
    assert "keep_wifi_connect" not in {e.key for e in entities}
    coordinator.watches["watch1"].settings["keep_wifi_connect"] = "0"
    coordinator.async_update_listeners()
    assert "keep_wifi_connect" in {e.key for e in entities}
    count = len(entities)
    coordinator.async_update_listeners()
    assert len(entities) == count


async def test_readback_overrides_requested_setting(coordinator):
    coordinator.client.read_settings.return_value = {"volume_level": "4"}
    await coordinator.async_set_setting("watch1", "volume_level", "2")
    coordinator.client.set_setting.assert_awaited_once_with("watch1", "group1", "volume_level", "2")
    assert coordinator.watches["watch1"].settings["volume_level"] == "4"


async def test_firmware_response_updates_sensor(coordinator):
    coordinator.client.command.return_value = {
        "CID": 30012, "RC": 1,
        "PL": {"sub_action": 504, "watch_version": "synthetic-v2"},
    }
    await coordinator.async_command("watch1", 504)
    entities = await all_entities(coordinator)
    firmware = next(entity for entity in entities if entity.key == "VersionCur")
    assert firmware.native_value == "synthetic-v2"


async def test_removed_watch_entities_become_unavailable(coordinator):
    entities = await all_entities(coordinator)
    coordinator.client.discover.return_value = []
    await coordinator._async_update_data()
    assert not any(entity.available for entity in entities)
    with pytest.raises(HomeAssistantError):
        await coordinator.async_command("watch1", 158)


async def test_auth_failure_becomes_ha_reauth(coordinator):
    coordinator.client.connect.side_effect = AuthenticationError("session expired")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_one_watch_failure_does_not_hide_other_watches(coordinator):
    coordinator.client.discover.return_value.append({"EID": "watch2", "GID": "g2"})
    coordinator.client.read_settings.side_effect = [
        ConnectionError("timeout"),
        {"battery_level": "50"},
    ]
    data = await coordinator._async_update_data()
    assert data["watch1"].settings_ok is False
    assert data["watch2"].settings_ok is True


async def test_diagnostics_never_include_private_payloads(coordinator):
    coordinator.watches["watch1"].settings["secret-token"] = "private-token"
    result = await async_get_config_entry_diagnostics(coordinator.hass, coordinator.entry)
    text = str(result)
    for private in (
        "private-email",
        "private-password",
        "private-account",
        "Private child",
        "watch1",
        "group1",
        "private-token",
        "secret-token",
        "1200",
    ):
        assert private not in text


def test_write_validation_rejects_unknown_and_out_of_range_values():
    assert validate_setting("volume_level", "2") == "2"
    assert validate_setting("steps_target_level", 8000) == "8000"
    for key, value in (
        ("volume_level", "9"),
        ("steps_target_level", "-1"),
        ("steps_target_level", "1234"),
        ("arbitrary_command", "1"),
    ):
        with pytest.raises(HomeAssistantError):
            validate_setting(key, value)

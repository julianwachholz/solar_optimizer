"""Deterministic priority cascade tests."""
from unittest.mock import patch

from homeassistant.core import State
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN

from .commons import *  # pylint: disable=wildcard-import, unused-wildcard-import


async def test_priority_cascade_limits_to_one_device_change_per_cycle(
    hass: HomeAssistant, init_solar_optimizer_central_config
):
    """Only one device should be switched per cycle, in priority order."""
    await create_test_input_boolean(hass, "fake_device_a", "A")
    await create_test_input_boolean(hass, "fake_device_b", "B")

    entry_a = MockConfigEntry(
        domain=DOMAIN,
        title="Equipement A",
        unique_id="eqtAUniqueId",
        data={
            CONF_NAME: "Equipement A",
            CONF_DEVICE_TYPE: CONF_DEVICE,
            CONF_ENTITY_ID: "input_boolean.fake_device_a",
            CONF_POWER_MAX: 1000,
            CONF_CHECK_USABLE_TEMPLATE: "{{ True }}",
            CONF_DURATION_MIN: 0.1,
            CONF_DURATION_STOP_MIN: 0.1,
            CONF_ACTION_MODE: CONF_ACTION_MODE_ACTION,
            CONF_ACTIVATION_SERVICE: "input_boolean/turn_on",
            CONF_DEACTIVATION_SERVICE: "input_boolean/turn_off",
        },
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        title="Equipement B",
        unique_id="eqtBUniqueId",
        data={
            CONF_NAME: "Equipement B",
            CONF_DEVICE_TYPE: CONF_DEVICE,
            CONF_ENTITY_ID: "input_boolean.fake_device_b",
            CONF_POWER_MAX: 800,
            CONF_CHECK_USABLE_TEMPLATE: "{{ True }}",
            CONF_DURATION_MIN: 0.1,
            CONF_DURATION_STOP_MIN: 0.1,
            CONF_ACTION_MODE: CONF_ACTION_MODE_ACTION,
            CONF_ACTIVATION_SERVICE: "input_boolean/turn_on",
            CONF_DEACTIVATION_SERVICE: "input_boolean/turn_off",
        },
    )
    await create_managed_device(hass, entry_a, "equipement_a")
    await create_managed_device(hass, entry_b, "equipement_b")

    priority_entity_a = search_entity(
        hass, "select.solar_optimizer_priority_equipement_a", SELECT_DOMAIN
    )
    priority_entity_b = search_entity(
        hass, "select.solar_optimizer_priority_equipement_b", SELECT_DOMAIN
    )
    priority_entity_a.select_option(PRIORITY_HIGH)
    priority_entity_b.select_option(PRIORITY_LOW)
    await hass.async_block_till_done()

    side_effects = SideEffects(
        {
            "sensor.fake_power_consumption": State("sensor.fake_power_consumption", -1500),
            "sensor.fake_power_production": State("sensor.fake_power_production", 1500),
            "sensor.fake_battery_charge_power": State("sensor.fake_battery_charge_power", 0),
            "input_number.fake_sell_cost": State("input_number.fake_sell_cost", 1),
            "input_number.fake_buy_cost": State("input_number.fake_buy_cost", 1),
            "input_number.fake_sell_tax_percent": State("input_number.fake_sell_tax_percent", 0),
            "sensor.fake_battery_soc": State("sensor.fake_battery_soc", 0),
        },
        State("unknown.entity_id", "unknown"),
    )
    coordinator = SolarOptimizerCoordinator.get_coordinator()
    with patch("homeassistant.core.StateMachine.get", side_effect=side_effects.get_side_effects()):
        await coordinator._async_update_data()
        await hass.async_block_till_done()
        assert hass.states.get("input_boolean.fake_device_a").state == STATE_ON
        assert hass.states.get("input_boolean.fake_device_b").state == STATE_OFF

        await coordinator._async_update_data()
        await hass.async_block_till_done()
        assert hass.states.get("input_boolean.fake_device_b").state == STATE_ON


@pytest.mark.parametrize(
    "battery_mode,is_activated",
    [
        (BATTERY_MODE_FIRST, False),
        (BATTERY_MODE_LAST, True),
    ],
)
async def test_battery_mode_changes_virtual_surplus(
    hass: HomeAssistant, battery_mode, is_activated
):
    """battery_last should ignore battery power in surplus calculation."""
    entry_central = MockConfigEntry(
        domain=DOMAIN,
        title="Central",
        unique_id=f"central-{battery_mode}",
        data={
            CONF_NAME: "Configuration",
            CONF_REFRESH_PERIOD_SEC: 60,
            CONF_DEVICE_TYPE: CONF_DEVICE_CENTRAL,
            CONF_POWER_CONSUMPTION_ENTITY_ID: "sensor.fake_power_consumption",
            CONF_POWER_PRODUCTION_ENTITY_ID: "sensor.fake_power_production",
            CONF_SELL_COST_ENTITY_ID: "input_number.fake_sell_cost",
            CONF_BUY_COST_ENTITY_ID: "input_number.fake_buy_cost",
            CONF_SELL_TAX_PERCENT_ENTITY_ID: "input_number.fake_sell_tax_percent",
            CONF_SMOOTH_PRODUCTION: True,
            CONF_BATTERY_SOC_ENTITY_ID: "sensor.fake_battery_soc",
            CONF_BATTERY_CHARGE_POWER_ENTITY_ID: "sensor.fake_battery_charge_power",
            CONF_BATTERY_MODE: battery_mode,
            CONF_RAZ_TIME: "05:00",
        },
    )
    await create_managed_device(hass, entry_central, f"central-{battery_mode}")
    await create_test_input_boolean(hass, "fake_device_a", "A")

    entry_a = MockConfigEntry(
        domain=DOMAIN,
        title="Equipement A",
        unique_id=f"eqtA-{battery_mode}",
        data={
            CONF_NAME: "Equipement A",
            CONF_DEVICE_TYPE: CONF_DEVICE,
            CONF_ENTITY_ID: "input_boolean.fake_device_a",
            CONF_POWER_MAX: 1000,
            CONF_CHECK_USABLE_TEMPLATE: "{{ True }}",
            CONF_DURATION_MIN: 0.1,
            CONF_DURATION_STOP_MIN: 0.1,
            CONF_ACTION_MODE: CONF_ACTION_MODE_ACTION,
            CONF_ACTIVATION_SERVICE: "input_boolean/turn_on",
            CONF_DEACTIVATION_SERVICE: "input_boolean/turn_off",
        },
    )
    await create_managed_device(hass, entry_a, "equipement_a")

    side_effects = SideEffects(
        {
            "sensor.fake_power_consumption": State("sensor.fake_power_consumption", -600),
            "sensor.fake_power_production": State("sensor.fake_power_production", 600),
            "sensor.fake_battery_charge_power": State("sensor.fake_battery_charge_power", -600),
            "input_number.fake_sell_cost": State("input_number.fake_sell_cost", 1),
            "input_number.fake_buy_cost": State("input_number.fake_buy_cost", 1),
            "input_number.fake_sell_tax_percent": State("input_number.fake_sell_tax_percent", 0),
            "sensor.fake_battery_soc": State("sensor.fake_battery_soc", 0),
        },
        State("unknown.entity_id", "unknown"),
    )

    coordinator = SolarOptimizerCoordinator.get_coordinator()
    with patch("homeassistant.core.StateMachine.get", side_effect=side_effects.get_side_effects()):
        await coordinator._async_update_data()
        await hass.async_block_till_done()
        assert (hass.states.get("input_boolean.fake_device_a").state == STATE_ON) == is_activated

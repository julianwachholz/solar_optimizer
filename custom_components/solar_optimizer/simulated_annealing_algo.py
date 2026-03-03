"""Deterministic priority cascade algorithm."""
import logging

from .managed_device import ManagedDevice

_LOGGER = logging.getLogger(__name__)


class SimulatedAnnealingAlgorithm:
    """Keep historical class name but run a deterministic priority cascade."""

    def __init__(
        self,
        initial_temp: float,
        min_temp: float,
        cooling_factor: float,
        max_iteration_number: int,
    ):
        """Keep compatibility with existing YAML options."""
        _LOGGER.info(
            "Initializing deterministic algorithm (legacy args ignored): initial_temp=%.2f min_temp=%.2f cooling_factor=%.2f max_iterations_number=%d",
            initial_temp,
            min_temp,
            cooling_factor,
            max_iteration_number,
        )

    def _nominal_power(self, device: ManagedDevice) -> float:
        if device.can_change_power:
            return float(max(device.power_min, 0))
        return float(max(device.power_max, 0))

    def _variable_requested_power(self, available_power: float, device: ManagedDevice) -> int | None:
        power_min = int(max(device.power_min, 0))
        power_max = int(max(device.power_max, power_min))
        requested = int(max(power_min, min(power_max, available_power)))
        return requested if requested >= power_min else None

    def recuit_simule(
        self,
        devices: list[ManagedDevice],
        power_consumption: float,
        solar_power_production: float,  # pylint: disable=unused-argument
        sell_cost: float,  # pylint: disable=unused-argument
        buy_cost: float,  # pylint: disable=unused-argument
        sell_tax_percent: float,  # pylint: disable=unused-argument
        battery_soc: float,  # pylint: disable=unused-argument
        priority_weight: int,  # pylint: disable=unused-argument
    ):
        """Evaluate devices with a strict deterministic priority cascade."""
        if len(devices) <= 0 or power_consumption is None:
            _LOGGER.info(
                "Missing inputs for deterministic calculation. Calculation is abandoned"
            )
            return [], -1, -1

        current_import = max(0.0, power_consumption)
        current_export = max(0.0, -power_consumption)
        virtual_surplus = current_export - current_import

        best_solution: list[dict] = []
        by_name: dict[str, dict] = {}
        for device in devices:
            if not device.is_enabled:
                continue
            device.set_battery_soc(battery_soc)
            force_state = (
                False
                if device.is_active and ((not device.is_usable and not device.is_waiting) or device.current_power <= 0)
                else device.is_active
            )
            equipment = {
                "power_max": device.power_max,
                "power_min": device.power_min,
                "power_step": device.power_step,
                "current_power": device.current_power,
                "requested_power": device.current_power if force_state else 0,
                "name": device.name,
                "state": force_state,
                "is_usable": device.is_usable,
                "is_waiting": device.is_waiting,
                "can_change_power": device.can_change_power,
                "priority": device.priority,
            }
            best_solution.append(equipment)
            by_name[device.name] = equipment
            if force_state:
                virtual_surplus += device.current_power

        sorted_devices = sorted(
            [device for device in devices if device.is_enabled],
            key=lambda item: (item.priority, item.name),
        )

        for device in sorted_devices:
            equipment = by_name[device.name]
            nominal_power = self._nominal_power(device)
            is_active = equipment["state"]

            if not is_active:
                if not equipment["is_usable"]:
                    continue
                if device.can_change_power:
                    requested_power = self._variable_requested_power(virtual_surplus, device)
                    if requested_power is None:
                        continue
                    equipment["state"] = True
                    equipment["requested_power"] = requested_power
                    break

                if virtual_surplus >= nominal_power:
                    equipment["state"] = True
                    equipment["requested_power"] = nominal_power
                    break
                continue

            if (
                not device.should_be_forced_offpeak
                and not equipment["is_waiting"]
                and virtual_surplus < nominal_power
            ):
                equipment["state"] = False
                equipment["requested_power"] = 0
                break

            if device.can_change_power and equipment["is_usable"]:
                requested_power = self._variable_requested_power(virtual_surplus, device)
                if requested_power is not None and requested_power != device.current_power:
                    equipment["requested_power"] = requested_power
                    break

            virtual_surplus -= device.current_power

        total_power = sum(
            equipment["requested_power"]
            for equipment in best_solution
            if equipment["state"]
        )
        return best_solution, 0, total_power

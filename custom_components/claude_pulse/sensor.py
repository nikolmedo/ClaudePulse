"""Sensor platform for Claude Pulse."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_FABLE_QUOTA,
    DEFAULT_FABLE_QUOTA,
    DEFAULT_NAME,
    DOMAIN,
    LEGACY_ENTRY_TITLE,
)
from .coordinator import ClaudePulseCoordinator


@dataclass(frozen=True)
class ClaudePulseSensorDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with the coordinator data key."""

    data_key: str = ""


SENSOR_DESCRIPTIONS: tuple[ClaudePulseSensorDescription, ...] = (
    ClaudePulseSensorDescription(
        key="session_pct",
        data_key="session_pct",
        name="Session Usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-arc",
    ),
    ClaudePulseSensorDescription(
        key="weekly_pct",
        data_key="weekly_pct",
        name="Weekly Usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-bar",
    ),
    ClaudePulseSensorDescription(
        key="session_countdown",
        data_key="session_reset_countdown",
        name="Session Reset Countdown",
        icon="mdi:timer-outline",
    ),
    ClaudePulseSensorDescription(
        key="session_reset_time",
        data_key="session_reset_time",
        name="Session Reset Time",
        icon="mdi:clock-outline",
    ),
    ClaudePulseSensorDescription(
        key="weekly_reset",
        data_key="weekly_reset",
        name="Weekly Reset",
        icon="mdi:calendar-clock",
    ),
    ClaudePulseSensorDescription(
        key="weekly_reset_weekday",
        data_key="weekly_reset_weekday",
        name="Weekly Reset Weekday",
        icon="mdi:calendar-week",
    ),
    ClaudePulseSensorDescription(
        key="weekly_reset_time",
        data_key="weekly_reset_time",
        name="Weekly Reset Time",
        icon="mdi:clock-check-outline",
    ),
    ClaudePulseSensorDescription(
        key="session_used",
        data_key="session_used",
        name="Session Used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
    ),
    ClaudePulseSensorDescription(
        key="session_limit",
        data_key="session_limit",
        name="Session Limit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge-full",
    ),
    ClaudePulseSensorDescription(
        key="plan",
        data_key="plan",
        name="Plan",
        icon="mdi:card-account-details-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ClaudePulseSensorDescription(
        key="fable_pct",
        data_key="fable_pct",
        name="Fable Usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:book-open-variant",
    ),
    ClaudePulseSensorDescription(
        key="fable_reset",
        data_key="fable_reset",
        name="Fable Reset",
        icon="mdi:calendar-clock",
    ),
)

# Sensor data keys gated behind the optional Fable quota toggle.
FABLE_DATA_KEYS = frozenset({"fable_pct", "fable_reset"})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Claude Pulse sensors from a config entry."""
    coordinator: ClaudePulseCoordinator = hass.data[DOMAIN][entry.entry_id]
    fable_enabled = entry.data.get(CONF_FABLE_QUOTA, DEFAULT_FABLE_QUOTA)
    async_add_entities(
        ClaudePulseSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
        if description.data_key not in FABLE_DATA_KEYS or fable_enabled
    )


def _device_name(entry: ConfigEntry) -> str:
    """Name the device after the config entry so several accounts are distinguishable.

    Entries created before the name field existed carry the legacy title and
    keep the original device name, so nothing changes for existing setups.
    """
    title = (entry.title or "").strip()
    if not title or title == LEGACY_ENTRY_TITLE:
        return DEFAULT_NAME
    return title


class ClaudePulseSensor(CoordinatorEntity[ClaudePulseCoordinator], SensorEntity):
    """A single Claude Pulse sensor backed by the shared coordinator."""

    entity_description: ClaudePulseSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ClaudePulseCoordinator,
        entry: ConfigEntry,
        description: ClaudePulseSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=_device_name(entry),
            manufacturer="nolmedo.dev",
            model="Claude.ai Usage Monitor",
            entry_type="service",
            configuration_url="https://claude.ai/settings/usage",
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value from the latest coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)

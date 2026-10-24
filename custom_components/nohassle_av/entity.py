"""Device identity shared by every matrix entity."""

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

MANUFACTURER = "No Hassle AV"
MODEL = "8×8 HDMI Matrix"


def matrix_device_identifier(entry_id: str) -> tuple[str, str]:
    """The device registry identifier for one matrix config entry."""
    return (DOMAIN, f"matrix_{entry_id}")


def matrix_device_info(entry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={matrix_device_identifier(entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=entry.title,
    )

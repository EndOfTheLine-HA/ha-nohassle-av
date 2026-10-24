"""Constants for the No Hassle AV HDMI matrix integration."""

DOMAIN = "nohassle_av"

# Matrix entries created before the rename live in this domain, as entries with
# data["device_type"] == "matrix". They are moved here by migration.py.
LEGACY_DOMAIN = "monoprice"
LEGACY_DEVICE_TYPE = "matrix"

CONF_HOST = "host"
CONF_HTTP_PORT = "http_port"
CONF_INPUT_NAMES = "input_names"
# Set only on an entry created by the import flow; cleared once its entities,
# device and legacy entry have been moved.
CONF_MIGRATED_FROM = "migrated_from"
CONF_LEGACY_ENTRY_ID = "legacy_entry_id"

DEFAULT_HTTP_PORT = 80
INPUT_COUNT = 8

PLATFORMS = ["select", "button", "binary_sensor"]

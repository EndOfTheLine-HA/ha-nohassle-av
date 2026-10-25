"""Constants for the No Hassle AV HDMI matrix integration."""

DOMAIN = "nohassle_av"

CONF_HOST = "host"
CONF_HTTP_PORT = "http_port"
CONF_INPUT_NAMES = "input_names"
# Written by the 0.3.x import and removed once it finished. 0.4.0 no longer imports
# anything; it only warns if an entry still carries the marker.
CONF_IMPORT_MARKER = "migrated_from"

DEFAULT_HTTP_PORT = 80
INPUT_COUNT = 8

PLATFORMS = ["select", "button", "binary_sensor"]

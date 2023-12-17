"""Constants for Roborock."""
from vacuum_map_parser_base.config.drawable import Drawable

from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"
CONF_MAP_SPECIFIC_CONFIG = "map_specific_config"
CONF_MAP_COLOR_PALETTE = "map_color_palette"

CONF_MAP_CONFIG_ROOM_COLORS = "room_colors"
CONF_MAP_CONFIG_SCALE = "scale"
CONF_MAP_CONFIG_ROTATION = "rotation"
CONF_MAP_CONFIG_TRIM = "trim"

PLATFORMS = [
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.VACUUM,
]

IMAGE_DRAWABLES: list[Drawable] = [
    Drawable.PATH,
    Drawable.CHARGER,
    Drawable.VACUUM_POSITION,
]

IMAGE_CACHE_INTERVAL = 90

MAP_SLEEP = 3

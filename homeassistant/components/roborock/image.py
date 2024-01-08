"""Support for Roborock image."""
import asyncio
import io
from itertools import chain
from typing import Any

from roborock import RoborockCommand
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig, TrimConfig
from vacuum_map_parser_base.config.size import Sizes
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ROTATE,
    CONF_SCALE,
    CONF_TRIM_BOTTOM,
    CONF_TRIM_LEFT,
    CONF_TRIM_RIGHT,
    CONF_TRIM_TOP,
    DEFAULT_DRAWABLES,
    DEFAULT_SIZES,
    DOMAIN,
    DRAWABLE_COLORS,
    DRAWABLES,
    IMAGE_CACHE_INTERVAL,
    IMAGE_CONFIG,
    MAP_SLEEP,
    SIZES,
)
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock image platform."""

    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    sizes = Sizes({**DEFAULT_SIZES, **config_entry.options.get(SIZES, {})})
    drawables = [
        drawable
        for drawable, default_value in DEFAULT_DRAWABLES.items()
        if config_entry.options.get(DRAWABLES, {}).get(drawable, default_value)
    ]
    entities = list(
        chain.from_iterable(
            await asyncio.gather(
                *(
                    create_coordinator_maps(coord, sizes, drawables, config_entry)
                    for coord in coordinators.values()
                )
            )
        )
    )
    async_add_entities(entities)


class RoborockMap(RoborockCoordinatedEntity, ImageEntity):
    """A class to let you visualize the map."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        map_flag: int,
        starting_map: bytes,
        map_name: str,
        colors: ColorsPalette,
        sizes: Sizes,
        drawables: list[Drawable],
        image_config: ImageConfig,
    ) -> None:
        """Initialize a Roborock map."""
        RoborockCoordinatedEntity.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_name = map_name
        self.parser = RoborockMapDataParser(colors, sizes, drawables, image_config, [])
        self._attr_image_last_updated = dt_util.utcnow()
        self.map_flag = map_flag
        self.cached_map = self._create_image(starting_map)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_selected(self) -> bool:
        """Return if this map is the currently selected map."""
        return self.map_flag == self.coordinator.current_map

    def is_map_valid(self) -> bool:
        """Update this map if it is the current active map, and the vacuum is cleaning."""
        return (
            self.is_selected
            and self.image_last_updated is not None
            and self.coordinator.roborock_device_info.props.status is not None
            and bool(self.coordinator.roborock_device_info.props.status.in_cleaning)
        )

    def _handle_coordinator_update(self):
        # Bump last updated every third time the coordinator runs, so that async_image
        # will be called and we will evaluate on the new coordinator data if we should
        # update the cache.
        if (
            dt_util.utcnow() - self.image_last_updated
        ).total_seconds() > IMAGE_CACHE_INTERVAL and self.is_map_valid():
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Update the image if it is not cached."""
        if self.is_map_valid():
            map_data: bytes = await self.cloud_api.get_map_v1()
            self.cached_map = self._create_image(map_data)
        return self.cached_map

    def _create_image(self, map_bytes: bytes) -> bytes:
        """Create an image using the map parser."""
        parsed_map = self.parser.parse(map_bytes)
        if parsed_map.image is None:
            raise HomeAssistantError(
                "Something went wrong creating the map",
                translation_domain=DOMAIN,
                translation_key="map_failure",
            )
        img_byte_arr = io.BytesIO()
        parsed_map.image.data.save(img_byte_arr, format="PNG")
        return img_byte_arr.getvalue()


async def create_coordinator_maps(
    coord: RoborockDataUpdateCoordinator,
    sizes: Sizes,
    drawables: list[Drawable],
    config_entry: ConfigEntry,
) -> list[RoborockMap]:
    """Get the starting map information for all maps for this device. The following steps must be done synchronously.

    Only one map can be loaded at a time per device.
    """
    entities = []

    cur_map = coord.current_map
    # This won't be None at this point as the coordinator will have run first.
    assert cur_map is not None
    # Sort the maps so that we start with the current map and we can skip the
    # load_multi_map call.
    maps_info = sorted(
        coord.maps.items(), key=lambda data: data[0] == cur_map, reverse=True
    )
    for map_flag, map_name in maps_info:
        # Load the map - so we can access it with get_map_v1
        if map_flag != cur_map:
            # Only change the map and sleep if we have multiple maps.
            await coord.api.send_command(RoborockCommand.LOAD_MULTI_MAP, [map_flag])
            # We cannot get the map until the roborock servers fully process the
            # map change.
            await asyncio.sleep(MAP_SLEEP)
        # Get the map data
        api_data: bytes = await coord.cloud_api.get_map_v1()

        image_config_data: dict[str, Any] = config_entry.options.get(
            coord.get_config_entry_key_for_map(map_flag, IMAGE_CONFIG), {}
        )
        image_config = ImageConfig(
            scale=image_config_data.get(CONF_SCALE, 1),
            rotate=image_config_data.get(CONF_ROTATE, 0),
            trim=TrimConfig(
                left=image_config_data.get(CONF_TRIM_LEFT, 0),
                right=image_config_data.get(CONF_TRIM_RIGHT, 0),
                top=image_config_data.get(CONF_TRIM_TOP, 0),
                bottom=image_config_data.get(CONF_TRIM_BOTTOM, 0),
            ),
        )

        colors = ColorsPalette(
            colors_dict={
                **ColorsPalette().COLORS,
                **config_entry.options.get(DRAWABLE_COLORS, {}),
            }
        )

        entities.append(
            RoborockMap(
                f"{slugify(coord.roborock_device_info.device.duid)}_map_{map_name}",
                coord,
                map_flag,
                api_data,
                map_name,
                colors,
                sizes,
                drawables,
                image_config,
            )
        )
    if len(coord.maps) != 1:
        # Set the map back to the map the user previously had selected so that it
        # does not change the end user's app.
        # Only needs to happen when we changed maps above.
        await coord.cloud_api.send_command(RoborockCommand.LOAD_MULTI_MAP, [cur_map])
    return entities

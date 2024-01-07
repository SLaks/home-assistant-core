"""Config flow for Roborock."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from roborock.containers import UserData
from roborock.exceptions import (
    RoborockAccountDoesNotExist,
    RoborockException,
    RoborockInvalidCode,
    RoborockInvalidEmail,
    RoborockUrlException,
)
from roborock.web_api import RoborockApiClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_CODE,
    CONF_INCLUDE_SHARED,
    CONF_ROTATE,
    CONF_SCALE,
    CONF_TRIM_BOTTOM,
    CONF_TRIM_LEFT,
    CONF_TRIM_RIGHT,
    CONF_TRIM_TOP,
    CONF_USER_DATA,
    DEFAULT_DRAWABLES,
    DEFAULT_INCLUDE_SHARED,
    DEFAULT_SIZES,
    DEVICE_LIST,
    DEVICE_MAP_LIST,
    DEVICE_MAP_OPTIONS,
    DOMAIN,
    DRAWABLES,
    IMAGE_CONFIG,
    MAPS,
    ROOM_COLORS,
    SIZES,
)
from .coordinator import RoborockDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roborock."""

    VERSION = 1
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._client: RoborockApiClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            self._username = username
            _LOGGER.debug("Requesting code for Roborock account")
            self._client = RoborockApiClient(username)
            errors = await self._request_code()
            if not errors:
                return await self.async_step_code()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str}),
            errors=errors,
        )

    async def _request_code(self) -> dict:
        assert self._client
        errors: dict[str, str] = {}
        try:
            await self._client.request_code()
        except RoborockAccountDoesNotExist:
            errors["base"] = "invalid_email"
        except RoborockUrlException:
            errors["base"] = "unknown_url"
        except RoborockInvalidEmail:
            errors["base"] = "invalid_email_format"
        except RoborockException as ex:
            _LOGGER.exception(ex)
            errors["base"] = "unknown_roborock"
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(ex)
            errors["base"] = "unknown"
        return errors

    async def async_step_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        assert self._client
        assert self._username
        if user_input is not None:
            code = user_input[CONF_ENTRY_CODE]
            _LOGGER.debug("Logging into Roborock account using email provided code")
            try:
                login_data = await self._client.code_login(code)
            except RoborockInvalidCode:
                errors["base"] = "invalid_code"
            except RoborockException as ex:
                _LOGGER.exception(ex)
                errors["base"] = "unknown_roborock"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception(ex)
                errors["base"] = "unknown"
            else:
                if self.reauth_entry is not None:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry,
                        data={
                            **self.reauth_entry.data,
                            CONF_USER_DATA: login_data.as_dict(),
                        },
                    )
                    return self.async_abort(reason="reauth_successful")
                return self._create_entry(self._client, self._username, login_data)

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required(CONF_ENTRY_CODE): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._username = entry_data[CONF_USERNAME]
        assert self._username
        self._client = RoborockApiClient(self._username)
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._request_code()
            if not errors:
                return await self.async_step_code()
        return self.async_show_form(step_id="reauth_confirm", errors=errors)

    def _create_entry(
        self, client: RoborockApiClient, username: str, user_data: UserData
    ) -> FlowResult:
        """Finished config flow and create entry."""
        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_USER_DATA: user_data.as_dict(),
                CONF_BASE_URL: client.base_url,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return RoborockOptionsFlowHandler(config_entry)


IMAGE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCALE, default=1.0): vol.Coerce(float),
        vol.Optional(CONF_ROTATE, default=0): vol.In(
            [
                0,
                90,
                180,
                270,
            ]
        ),
        vol.Optional(CONF_TRIM_LEFT): vol.Coerce(float),
        vol.Optional(CONF_TRIM_RIGHT): vol.Coerce(float),
        vol.Optional(CONF_TRIM_TOP): vol.Coerce(float),
        vol.Optional(CONF_TRIM_BOTTOM): vol.Coerce(float),
    }
)


class RoborockOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle an option flow for Roborock."""

    devices: dict[str, RoborockDataUpdateCoordinator] = {}
    selected_device: RoborockDataUpdateCoordinator | None = None
    selected_map: int | None = None

    def get_placeholders(self):
        """Return translation placeholders for the selected map & device."""
        if self.selected_device is None or self.selected_map is None:
            raise ValueError("No map selected")
        return {
            "device_name": self.selected_device.roborock_device_info.device.name,
            "map_name": self.selected_device.maps[self.selected_map],
        }

    def get_selected_options_key(self, config_step: str):
        """Return the options dict for the selected map & device."""
        if self.selected_device is None or self.selected_map is None:
            raise ValueError("No map selected")
        return self.selected_device.get_config_entry_key_for_map(
            self.selected_map, config_step
        )

    def populate_dynamic_steps(self):
        """Create handler methods for dynamic steps for devices and maps."""
        self.devices = self.hass.data[DOMAIN][self.config_entry.entry_id]
        for duid, coord in self.devices.items():

            def device_step_handler(
                user_input: dict[str, Any] | None = None, device=coord
            ):
                """Select a device from the device list and show its next menu."""
                nonlocal coord
                # Set the current device so future steps can look it up.
                self.selected_device = device
                # Return the (hard-coded) submenu, with this device selected.
                return self.async_step_device_map_list()

            # Create the dynamic callback for the device-specific menu entry.
            setattr(self, f"async_step_device_map_list_{duid}", device_step_handler)

            for map_id in coord.maps:

                def map_step_handler(
                    user_input: dict[str, Any] | None = None, map_id=map_id
                ):
                    """Select a map from the map list and show its next menu."""
                    # Set the current map so future steps can look it up.
                    self.selected_map = map_id
                    # Return the (hard-coded) submenu, with this map selected.
                    return self.async_step_device_map_options()

                # Create the dynamic callback for the map-specific menu entry.
                setattr(
                    self,
                    f"async_step_device_map_options_{map_id}",
                    map_step_handler,
                )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the initial menu."""
        self.populate_dynamic_steps()

        return self.async_show_menu(
            step_id="init", menu_options=[DOMAIN, MAPS, DEVICE_LIST]
        )

    async def async_step_device_list(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show a list of devices to select a device-specific submenu."""
        if len(self.devices) == 1:
            # If there is only one device, skip this submenu.
            self.selected_device = list(self.devices.values())[0]
            return await self.async_step_device_map_list()
        return self.async_show_menu(
            step_id=DEVICE_LIST,
            # Generate a dict of options with dynamic names (that cannot involve translations).
            # These point to dynamic step handlers that store the selected device.
            # Future steps look up the selected device from our instance and are not otherwise dynamic.
            menu_options={
                f"device_map_list_{duid}": coord.roborock_device_info.device.name
                for duid, coord in self.devices.items()
            },
        )

    async def async_step_device_map_list(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show a list of maps on the selected device.

        This is used as the result for the dynamic callbacks above that select the device.
        """
        if self.selected_device is None:
            return self.async_abort(reason="no_device_selected")
        if len(self.selected_device.maps) == 1:
            # If there is only one device, skip this submenu.
            self.selected_map = list(self.selected_device.maps.keys())[0]
            return await self.async_step_device_map_options()
        return self.async_show_menu(
            # Use our fixed (non-dynamic) name for translations, and so that the data flow system recognizes it.
            step_id=DEVICE_MAP_LIST,
            # Generate a dict of options with dynamic names (that cannot involve translations).
            # These point to dynamic step handlers that store the selected device.
            # Future steps look up the selected device from our instance and are not otherwise dynamic.
            menu_options={
                f"device_map_options_{id}": name
                for id, name in self.selected_device.maps.items()
            },
            # Populate the selected device name for the subtitle.
            description_placeholders={
                "device_name": self.selected_device.roborock_device_info.device.name,
            },
        )

    async def async_step_device_map_options(self) -> FlowResult:
        """Create a menu of options for the selected map.

        This is used as the result for the dynamic callbacks above that select the map.
        """
        if self.selected_device is None or self.selected_map is None:
            return self.async_abort(reason="no_map_selected")
        return self.async_show_menu(
            # Use our fixed (non-dynamic) name for translations, and so that the data flow system recognizes it.
            step_id=DEVICE_MAP_OPTIONS,
            menu_options=[IMAGE_CONFIG, ROOM_COLORS],
            description_placeholders=self.get_placeholders(),
        )

    async def async_step_image_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the map object size options."""
        key = self.get_selected_options_key(IMAGE_CONFIG)
        current_config = self.config_entry.options.get(key, {})

        if user_input is not None:
            return self.update_config_entry_from_user_input(key, user_input)

        return self.async_show_form(
            step_id=IMAGE_CONFIG,
            data_schema=self.add_suggested_values_to_schema(
                IMAGE_CONFIG_SCHEMA, current_config
            ),
            description_placeholders=self.get_placeholders(),
        )

    async def async_step_roborock(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options domain wide."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **user_input}
            )
        return self.async_show_form(
            step_id=DOMAIN,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INCLUDE_SHARED,
                        default=self.config_entry.options.get(
                            CONF_INCLUDE_SHARED, DEFAULT_INCLUDE_SHARED
                        ),
                    ): bool
                }
            ),
        )

    async def async_step_maps(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Open the menu for the map options."""
        return self.async_show_menu(step_id=MAPS, menu_options=[DRAWABLES, SIZES])

    async def async_step_sizes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the map object size options."""
        if user_input is not None:
            return self.update_config_entry_from_user_input(SIZES, user_input)
        data_schema = {}
        for size, default_value in DEFAULT_SIZES.items():
            data_schema[
                vol.Required(
                    size.value,
                    default=self.config_entry.options.get(SIZES, {}).get(
                        size, default_value
                    ),
                )
            ] = vol.All(vol.Coerce(float), vol.Range(min=0))
        return self.async_show_form(
            step_id=SIZES,
            data_schema=vol.Schema(data_schema),
        )

    async def async_step_drawables(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the map object drawable options."""
        if user_input is not None:
            return self.update_config_entry_from_user_input(DRAWABLES, user_input)
        data_schema = {}
        for drawable, default_value in DEFAULT_DRAWABLES.items():
            data_schema[
                vol.Required(
                    drawable.value,
                    default=self.config_entry.options.get(DRAWABLES, {}).get(
                        drawable, default_value
                    ),
                )
            ] = bool
        return self.async_show_form(
            step_id=DRAWABLES,
            data_schema=vol.Schema(data_schema),
        )

    def update_config_entry_from_user_input(
        self,
        key: str,
        user_input: Mapping[str, Any],
    ) -> FlowResult:
        """Update an existing dict in the config entry from user input."""
        new_config = {
            key: {
                **self.config_entry.options.get(key, {}),
                **user_input,
            }
        }
        return self.async_create_entry(
            title="", data={**self.config_entry.options, **new_config}
        )

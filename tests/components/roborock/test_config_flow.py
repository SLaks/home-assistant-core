"""Test Roborock config flow."""
from copy import deepcopy
import dataclasses
from unittest.mock import patch

import pytest
from roborock.exceptions import (
    RoborockAccountDoesNotExist,
    RoborockException,
    RoborockInvalidCode,
    RoborockInvalidEmail,
    RoborockUrlException,
)
from vacuum_map_parser_base.config.color import ColorsPalette, SupportedColor
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.size import Size

from homeassistant import config_entries
from homeassistant.components.roborock.const import (
    CONF_ENTRY_CODE,
    CONF_INCLUDE_SHARED,
    CONF_ROTATE,
    DEVICE_LIST,
    DEVICE_MAP_LIST,
    DEVICE_MAP_OPTIONS,
    DOMAIN,
    DRAWABLE_COLORS,
    DRAWABLES,
    IMAGE_CONFIG,
    MAPS,
    SIZES,
)
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .mock_data import HOME_DATA, MOCK_CONFIG, MULTI_MAP_LIST, USER_DATA, USER_EMAIL

from tests.common import MockConfigEntry


async def test_config_flow_success(
    hass: HomeAssistant,
    bypass_api_fixture,
) -> None:
    """Handle the config flow and make sure it succeeds."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "code"
            assert result["errors"] == {}
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            return_value=USER_DATA,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "request_code_side_effect",
        "request_code_errors",
    ),
    [
        (RoborockException(), {"base": "unknown_roborock"}),
        (RoborockAccountDoesNotExist(), {"base": "invalid_email"}),
        (RoborockInvalidEmail(), {"base": "invalid_email_format"}),
        (RoborockUrlException(), {"base": "unknown_url"}),
        (Exception(), {"base": "unknown"}),
    ],
)
async def test_config_flow_failures_request_code(
    hass: HomeAssistant,
    bypass_api_fixture,
    request_code_side_effect: Exception | None,
    request_code_errors: dict[str, str],
) -> None:
    """Handle applying errors to request code recovering from the errors."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code",
            side_effect=request_code_side_effect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )
            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == request_code_errors
        # Recover from error
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "code"
            assert result["errors"] == {}
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            return_value=USER_DATA,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "code_login_side_effect",
        "code_login_errors",
    ),
    [
        (RoborockException(), {"base": "unknown_roborock"}),
        (RoborockInvalidCode(), {"base": "invalid_code"}),
        (Exception(), {"base": "unknown"}),
    ],
)
async def test_config_flow_failures_code_login(
    hass: HomeAssistant,
    bypass_api_fixture,
    code_login_side_effect: Exception | None,
    code_login_errors: dict[str, str],
) -> None:
    """Handle applying errors to code login and recovering from the errors."""
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_USERNAME: USER_EMAIL}
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "code"
            assert result["errors"] == {}
        # Raise exception for invalid code
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            side_effect=code_login_side_effect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == code_login_errors
        with patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
            return_value=USER_DATA,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]
    assert len(mock_setup.mock_calls) == 1


async def test_reauth_flow(
    hass: HomeAssistant, bypass_api_fixture, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test reauth flow."""
    # Start reauth
    result = mock_roborock_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    # Request a new code
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockApiClient.request_code"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    # Enter a new code
    assert result["step_id"] == "code"
    assert result["type"] == FlowResultType.FORM
    new_user_data = deepcopy(USER_DATA)
    new_user_data.rriot.s = "new_password_hash"
    with patch(
        "homeassistant.components.roborock.config_flow.RoborockApiClient.code_login",
        return_value=new_user_data,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_roborock_entry.data["user_data"]["rriot"]["s"] == "new_password_hash"


async def test_options_flow_domain(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow works."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DOMAIN},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == DOMAIN
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_INCLUDE_SHARED: True},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options[CONF_INCLUDE_SHARED] is True
    assert len(mock_setup.mock_calls) == 1


async def test_options_flow_drawables(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow works."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": MAPS},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == MAPS
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DRAWABLES},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == DRAWABLES
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={Drawable.PREDICTED_PATH: True},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options[DRAWABLES][Drawable.PREDICTED_PATH] is True
    assert len(mock_setup.mock_calls) == 1


async def test_options_flow_drawable_colors(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow works."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": MAPS},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == MAPS
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DRAWABLE_COLORS},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == DRAWABLE_COLORS

    form_values = {v.schema: v.default() for v in result["data_schema"].schema}
    # Apply defaults from ColorPalette
    assert form_values[SupportedColor.MAP_INSIDE] == [32, 115, 185]
    # Drop the alpha value
    assert form_values[SupportedColor.CHARGER] == [0x66, 0xFE, 0xDA]

    # Hide colors for drawables & their outlines if they're disabled by default.
    assert SupportedColor.IGNORED_OBSTACLE not in form_values
    assert SupportedColor.NO_GO_ZONES_OUTLINE not in form_values
    assert SupportedColor.NO_MOPPING_ZONES not in form_values

    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                SupportedColor.MAP_INSIDE: [255, 0, 0],
                SupportedColor.CHARGER: [0, 255, 0],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options[DRAWABLE_COLORS][SupportedColor.MAP_INSIDE] == (
        255,
        0,
        0,
    )
    # Re-apply alpha to edited color
    assert setup_entry.options[DRAWABLE_COLORS][SupportedColor.CHARGER] == (
        0,
        255,
        0,
        0x7F,
    )
    # Preserve unchanged values, with alpha.
    assert (
        setup_entry.options[DRAWABLE_COLORS][SupportedColor.CHARGER_OUTLINE]
        == ColorsPalette().COLORS[SupportedColor.CHARGER_OUTLINE]
    )

    assert len(mock_setup.mock_calls) == 1


async def test_options_flow_sizes(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow works."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": MAPS},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == MAPS
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": SIZES},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SIZES
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={Size.PATH_WIDTH: 3.2},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options[SIZES][Size.PATH_WIDTH] == 3.2
    assert len(mock_setup.mock_calls) == 1


SINGLE_MAP_LIST = dataclasses.replace(
    MULTI_MAP_LIST, map_info=[MULTI_MAP_LIST.map_info[0]]
)
SINGLE_DEVICE_DATA = dataclasses.replace(HOME_DATA, devices=[HOME_DATA.devices[0]])


@pytest.mark.home_data(SINGLE_DEVICE_DATA)
@pytest.mark.multi_map_list(SINGLE_MAP_LIST)
async def test_options_flow_one_device_one_map(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow skips the map and device submenus."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DEVICE_LIST},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_MAP_OPTIONS
    assert result["description_placeholders"] == {
        "device_name": "Roborock S7 MaxV",
        "map_name": "Upstairs",
    }


@pytest.mark.multi_map_list(SINGLE_MAP_LIST)
async def test_options_flow_two_devices_one_map(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow skips the map submenu."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DEVICE_LIST},
    )

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_LIST
    assert result["menu_options"] == {
        "device_map_list_abc123": "Roborock S7 MaxV",
        "device_map_list_device_2": "Roborock S7 2",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "device_map_list_device_2"},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_MAP_OPTIONS
    assert result["description_placeholders"] == {
        "device_name": "Roborock S7 2",
        "map_name": "Upstairs",
    }


@pytest.mark.home_data(SINGLE_DEVICE_DATA)
async def test_options_flow_one_device_two_maps(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow skips the device submenu."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DEVICE_LIST},
    )

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_MAP_LIST
    assert result["description_placeholders"] == {
        "device_name": "Roborock S7 MaxV",
    }
    assert result["menu_options"] == {
        "device_map_options_0": "Upstairs",
        "device_map_options_1": "Downstairs",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "device_map_options_1"},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_MAP_OPTIONS
    assert result["description_placeholders"] == {
        "device_name": "Roborock S7 MaxV",
        "map_name": "Downstairs",
    }


async def test_options_flow_two_devices_two_maps(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow shows the device and map submenus."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DEVICE_LIST},
    )

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_LIST
    assert result["menu_options"] == {
        "device_map_list_abc123": "Roborock S7 MaxV",
        "device_map_list_device_2": "Roborock S7 2",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "device_map_list_device_2"},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_MAP_LIST
    assert result["description_placeholders"] == {
        "device_name": "Roborock S7 2",
    }
    assert result["menu_options"] == {
        "device_map_options_0": "Upstairs",
        "device_map_options_1": "Downstairs",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "device_map_options_1"},
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == DEVICE_MAP_OPTIONS
    assert result["description_placeholders"] == {
        "device_name": "Roborock S7 2",
        "map_name": "Downstairs",
    }


@pytest.mark.home_data(SINGLE_DEVICE_DATA)  # Skip menu steps
@pytest.mark.multi_map_list(SINGLE_MAP_LIST)
async def test_options_flow_image_config(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow saves image config."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": DEVICE_LIST},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": IMAGE_CONFIG},
    )
    assert result["type"] == FlowResultType.FORM
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ROTATE: 270},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options["device.abc123.map.0.image_config"][CONF_ROTATE] == 270
    assert len(mock_setup.mock_calls) == 1

"""Config flow for nrgi_prices integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REGIONS = ["DK1", "DK2"]

class ConfigFlow(config_entries.ConfigFlow,  domain=DOMAIN):

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validate the user input.
            region = user_input.get("region")
            if region not in REGIONS:
                errors["region"] = "invalid_region"

            region_already_configured = any(
                entry.data["region"] == region
                for entry in self._async_current_entries()
            )

            if region_already_configured:
                errors["region"] = "region_already_configured"

            # If the input is valid, store it and move on to the next step.
            if not errors:
                return self.async_create_entry(title=f"NRGI Price - {region}", data=user_input)

        none_used_regions = [
            region
            for region in REGIONS
            if region not in [entry.data["region"] for entry in self._async_current_entries()]
        ]

        if len(none_used_regions) == 0:
            errors["base"] = "Both regions have already been used"
            return self.async_show_form(
                step_id="user",
                errors=errors,
            )

        # If there are errors, or no input has been received yet, show the form.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("region", default=none_used_regions[0]): vol.In(none_used_regions)
                }
            ),
            errors=errors,
        )

"""Platform for Eloverblik sensor integration."""
from datetime import datetime, timedelta, timezone
import logging
from typing import Literal, Optional, Union
from . import HassNrgi, FullPriceResult
from homeassistant.helpers import config_entry_flow

Any = object()
from pydantic import BaseModel, Field
import requests

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DOMAIN

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)
NRGI_PRICE_ENDPOINT = "https://nrgi.dk/api/common/pricehistory"

timezone_offset = +1.0  # Pacific Standard Time (UTC−08:00)
tzinfo = timezone(timedelta(hours=timezone_offset))


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the sensor platform."""
    hass_nrgi = hass.data[DOMAIN][config.entry_id]

    sensors = []

    sensors.append(NrgiPrice(
        hass_nrgi=hass_nrgi,
    ))

    async_add_entities(sensors)


class NrgiPrice(Entity):
    """Representation of an energy sensor."""

    def __init__(
        self,
        hass_nrgi: HassNrgi,
    ):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}

        self._hass_nrgi: HassNrgi = hass_nrgi

        self._name = f"NRGI Price {self._hass_nrgi.region}"
        self._unique_id = f"nrgi_price_{self._hass_nrgi.region}"
        self._price_data: Optional[FullPriceResult] = None



    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""

        return self._state

    @property
    def state_attributes(self) -> Optional[dict[str, Any]]:
        """Return the state attributes.

        Implemented by component base class, should not be extended by integrations.
        Convention for attribute names is lowercase snake_case.
        """
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "DKK/kWh"

    def get_attributes(self):
        days = {
            "raw_today": self._hass_nrgi.today_data,
            "raw_tomorrow": self._hass_nrgi.tomorrow_data
        }

        attributes = {
            "raw_today": [],
            "raw_tomorrow": [],
        }

        for day, full_price_result in days.items():
          price_points_attributes = list(map(lambda price_point: {
            "start": price_point.local_time,
            "price_inc_vat": price_point.price_inc_vat  / 100,
            "raw_price_inc_vat": price_point.raw_price_inc_vat  / 100,
            "value": price_point.value  / 100,
            "is_highest_price": price_point.is_highest_price,
            "is_lowest_price": price_point.is_lowest_price
          }, full_price_result.prices))

          attributes[day] = price_points_attributes

        return attributes

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._hass_nrgi.update_prices()

        # Update the attibutes
        self._attributes = self.get_attributes()

        # Update the state
        current_hour = datetime.now(tzinfo).hour

        price_now = self._hass_nrgi.today_data.prices[current_hour].value  / 100
        self._state = (price_now)

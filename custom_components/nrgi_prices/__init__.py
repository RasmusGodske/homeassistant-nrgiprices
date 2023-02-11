"""The nrgi_prices integration."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pydantic import BaseModel, Field
import requests
import logging

from homeassistant.util import Throttle
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up nrgi_prices from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    # TODO 1. Create API instance
    # TODO 2. Validate the API connection (and authentication)
    # TODO 3. Store an API object for your platforms to access

    hass.data[DOMAIN][entry.entry_id] = HassNrgi(region=entry.data['region'])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PriceEntry(BaseModel):
    is_highest_price: bool = Field(..., alias="isHighestPrice")
    is_lowest_price: bool = Field(..., alias="isLowestPrice")
    local_time: datetime = Field(..., alias="localTime")
    price_inc_vat: float = Field(..., alias="priceInclVat")
    raw_price_inc_vat: float = Field(..., alias="rawPriceInclVat")
    value: float = Field(..., alias="value")


class FullPriceResult(BaseModel):
    average_price: str = Field(None, alias="averagePrice")
    current_price: str = Field(None, alias="currentPrice")
    date: str = Field(None, alias="date")
    highest_price: str = Field(None, alias="highestPrice")
    lowest_price: str = Field(None, alias="lowestPrice")
    prices: list[PriceEntry] = Field(None, alias="prices")
    region: str = Field(None, alias="region")


class HassNrgi:
    """Class to fetch and store data from Nrgi.dk."""

    def __init__(self, region: str = "DK1") -> None:
        """Initialize the data object."""
        self.today_data: FullPriceResult = {}
        self.tomorrow_data: FullPriceResult = {}
        self.region: str = region

    def get_today_price_at_hour(self, hour: int) -> float:
        """Get today's price at a specific hour."""
        return self.today_data.prices[hour].price_inc_vat

    def get_tomorrows_price_at_hour(self, hour: int) -> float:
        """Get today's price at a specific hour."""
        return self.tomorrow_data.prices[hour].price_inc_vat

    def fetch_prices_for_day(self, date: datetime, region: str) -> float:
        """Fetch price for a specific date."""

        params = {
            "region": self.region,
            "date": date.strftime("%Y-%m-%d"),
        }

        response = requests.get(
            "https://nrgi.dk/api/common/pricehistory",
            params=params,
            timeout=10,
        )

        _LOGGER.debug("Fetching energy price from Nrgi.dk")

        return FullPriceResult(**response.json())

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_prices(self):
        """Fetch new prices from Nrgi.dk."""

        _LOGGER.debug("Fetching energy price from Nrgi.dk")

        tzinfo = timezone(timedelta(hours=1))
        date_today = datetime.now(tzinfo)
        date_tomorrow = date_today + timedelta(days=1)

        prices_today = self.fetch_prices_for_day(date_today, self.region)
        prices_tomorrow = self.fetch_prices_for_day(date_tomorrow, self.region)

        self.today_data = prices_today
        self.tomorrow_data = prices_tomorrow

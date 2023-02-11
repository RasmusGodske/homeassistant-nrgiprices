"""The nrgi_prices integration."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pydantic import BaseModel, Field
import requests
import logging

from homeassistant.util import Throttle
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

timezone_offset = +1.0  # Europe/Copenhagen (UTC+01:00)
danish_tz = timezone(timedelta(hours=timezone_offset))

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up nrgi_prices from a config entry."""

    hass.data.setdefault(DOMAIN, {})

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
        self.today_data: Optional[FullPriceResult] = None
        self.tomorrow_data: Optional[FullPriceResult] = None
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
            "region": region,
            "date": date.strftime("%Y-%m-%d"),
        }

        response = requests.get(
            "https://nrgi.dk/api/common/pricehistory",
            params=params,
            timeout=10,
        )

        _LOGGER.debug("Fetching energy price from Nrgi.dk")

        return FullPriceResult(**response.json())

    def _tomorrow_data_available(self) -> bool:
        """Check if we should update the prices for tomorrow."""

        current_time = datetime.now(danish_tz)

        # Define 3 PM in the Danish timezone
        three_pm = current_time.replace(hour=15, minute=0, second=0, microsecond=0)

        if current_time > three_pm:
            return True

    def _should_update_tomorrow(self) -> bool:
        """Check if we should update the prices for tomorrow."""

        if not self._tomorrow_data_available():
            return False

        if self.tomorrow_data is None:
            return True

        return self.tomorrow_data.date != (
            datetime.now(danish_tz) + timedelta(days=1)
        ).strftime("%Y-%m-%d")

    def _update_tomorrow_prices(self):
        """Fetch new prices from Nrgi.dk."""

        # Data is only available after 3 PM in the Danish timezone
        if not self._tomorrow_data_available():
            self.tomorrow_data = None
            return

        if not self._should_update_tomorrow():
            return

        _LOGGER.debug("Fetching tomorrow's energy price from Nrgi.dk")

        date_tomorrow = datetime.now(danish_tz) + timedelta(days=1)

        prices_tomorrow = self.fetch_prices_for_day(date_tomorrow, self.region)

        self.tomorrow_data = prices_tomorrow

    def _should_update_today(self) -> bool:
        """Check if we should update the prices for today."""
        if self.today_data is None:
            return True

        return self.today_data.date != datetime.now(danish_tz).strftime("%Y-%m-%d")

    def _update_today_prices(self):
        """Fetch new prices from Nrgi.dk."""

        if not self._should_update_today():
            return

        _LOGGER.debug("Fetching today's energy price from Nrgi.dk")

        date_today = datetime.now(danish_tz)

        prices_today = self.fetch_prices_for_day(date_today, self.region)

        self.today_data = prices_today

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_prices(self):
        """Fetch new prices from Nrgi.dk."""

        self._update_today_prices()
        self._update_tomorrow_prices()

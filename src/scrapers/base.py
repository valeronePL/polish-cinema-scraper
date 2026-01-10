"""Base scraper interface."""

from abc import ABC, abstractmethod
from datetime import date

from src.models import Screening


class BaseScraper(ABC):
    """Abstract base class for cinema scrapers."""

    @property
    @abstractmethod
    def cinema_chain(self) -> str:
        """Name of the cinema chain."""
        ...

    @abstractmethod
    async def get_screenings(self, city: str, target_date: date) -> list[Screening]:
        """Fetch screenings for a specific city and date."""
        ...

    @abstractmethod
    async def get_cities(self) -> list[str]:
        """Get list of available cities."""
        ...

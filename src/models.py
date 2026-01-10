"""Data models for cinema screenings."""

from datetime import datetime
from pydantic import BaseModel


class Cinema(BaseModel):
    """Cinema venue information."""

    name: str
    city: str
    address: str | None = None
    website: str | None = None


class Screening(BaseModel):
    """Single movie screening."""

    movie_title: str
    cinema: Cinema
    datetime: datetime
    language: str = "pl"  # pl, dubbed, subtitled, original
    format: str = "2D"  # 2D, 3D, IMAX, etc.
    price: float | None = None
    booking_url: str | None = None


class Movie(BaseModel):
    """Movie information."""

    title: str
    original_title: str | None = None
    duration_minutes: int | None = None
    genre: list[str] = []
    rating: str | None = None  # age rating

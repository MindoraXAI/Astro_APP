"""
Location resolution utilities for birth-place driven chart requests.
"""
from __future__ import annotations

from functools import lru_cache

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from app.core.models import BirthData, LocationResolutionResponse


_geolocator = Nominatim(user_agent="ais-astro-app")
_timezone_finder = TimezoneFinder()


@lru_cache(maxsize=256)
def resolve_location_candidates(query: str, max_candidates: int = 5) -> list[LocationResolutionResponse]:
    locations = _geolocator.geocode(query, exactly_one=False, addressdetails=True, limit=max_candidates)
    if not locations:
        raise ValueError(f"Could not resolve place of birth: {query}")

    candidates: list[LocationResolutionResponse] = []
    for location in locations:
        timezone = _timezone_finder.timezone_at(lat=location.latitude, lng=location.longitude)
        if timezone is None:
            timezone = _timezone_finder.closest_timezone_at(lat=location.latitude, lng=location.longitude)
        if timezone is None:
            continue

        candidates.append(
            LocationResolutionResponse(
                query=query,
                latitude=location.latitude,
                longitude=location.longitude,
                timezone=timezone,
                display_name=location.address or query,
            )
        )

    if not candidates:
        raise ValueError(f"Could not determine timezone for: {query}")
    return candidates


@lru_cache(maxsize=256)
def resolve_location_query(query: str) -> LocationResolutionResponse:
    candidates = resolve_location_candidates(query)
    best = candidates[0]
    confidence = 1.0 if len(candidates) == 1 else max(0.5, 1 - (len(candidates) - 1) * 0.1)
    return best.model_copy(
        update={
            "confidence": confidence,
            "candidates_count": len(candidates),
        }
    )


def resolve_birth_data(birth_data: BirthData) -> BirthData:
    if birth_data.latitude is not None and birth_data.longitude is not None and birth_data.timezone:
        return birth_data

    if not birth_data.birth_place:
        raise ValueError(
            "Birth data is missing location details. Provide birth_place or latitude/longitude/timezone."
        )

    resolved = resolve_location_query(birth_data.birth_place)
    return birth_data.model_copy(
        update={
            "latitude": resolved.latitude,
            "longitude": resolved.longitude,
            "timezone": resolved.timezone,
            "birth_place": resolved.display_name,
        }
    )

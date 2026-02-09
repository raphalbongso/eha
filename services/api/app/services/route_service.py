"""Route/travel time service with Google Maps provider."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

GOOGLE_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


@dataclass
class TravelEstimate:
    """Travel time estimate between two locations."""

    origin: str
    destination: str
    mode: str  # "driving", "transit", "walking", "cycling"
    duration_minutes: float
    distance_km: float
    departure_time: str  # ISO8601


class RouteProvider(ABC):
    """Abstract base class for route providers."""

    @abstractmethod
    async def get_travel_time(
        self,
        origin: str,
        destination: str,
        mode: str = "driving",
    ) -> TravelEstimate:
        """Calculate travel time between two points."""
        ...


class GoogleMapsRouteProvider(RouteProvider):
    """Google Maps Directions API route provider."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def get_travel_time(
        self,
        origin: str,
        destination: str,
        mode: str = "driving",
    ) -> TravelEstimate:
        """Query Google Directions API for travel time.

        Args:
            origin: Starting address or "lat,lng".
            destination: Ending address or "lat,lng".
            mode: One of "driving", "transit", "walking", "bicycling".

        Returns:
            TravelEstimate with duration and distance.
        """
        # Google uses "bicycling" not "cycling"
        google_mode = "bicycling" if mode == "cycling" else mode

        params = {
            "origin": origin,
            "destination": destination,
            "mode": google_mode,
            "departure_time": "now",
            "key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(GOOGLE_DIRECTIONS_URL, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "OK" or not data.get("routes"):
            logger.warning("Google Directions API: status=%s for %s -> %s", data.get("status"), origin[:20], destination[:20])
            raise ValueError(f"No route found: {data.get('status')}")

        leg = data["routes"][0]["legs"][0]
        duration_seconds = leg["duration"]["value"]
        distance_meters = leg["distance"]["value"]

        # Use duration_in_traffic if available (driving mode only)
        if "duration_in_traffic" in leg:
            duration_seconds = leg["duration_in_traffic"]["value"]

        return TravelEstimate(
            origin=origin,
            destination=destination,
            mode=mode,
            duration_minutes=round(duration_seconds / 60, 1),
            distance_km=round(distance_meters / 1000, 2),
            departure_time=datetime.now(timezone.utc).isoformat(),
        )


def get_route_provider(settings: Settings) -> GoogleMapsRouteProvider | None:
    """Create a route provider if API key is configured."""
    api_key = settings.google_maps_api_key.get_secret_value()
    if not api_key:
        logger.info("Google Maps API key not configured; route provider disabled")
        return None
    return GoogleMapsRouteProvider(api_key)

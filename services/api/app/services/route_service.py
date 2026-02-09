"""Route/travel time service — v2 stub.

This module provides the interface for calculating travel times
between locations. Implementation will be added in v2 with
Google Maps, Apple Maps, or similar provider integration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


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
        """Calculate travel time between two points.

        Args:
            origin: Starting address or coordinates.
            destination: Ending address or coordinates.
            mode: Travel mode (driving, transit, walking, cycling).

        Returns:
            TravelEstimate with duration and distance.
        """
        raise NotImplementedError("v2: Route provider not yet implemented")

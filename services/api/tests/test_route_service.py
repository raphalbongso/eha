"""Unit tests for route_service (GoogleMapsRouteProvider, get_route_provider)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.route_service import (
    GoogleMapsRouteProvider,
    TravelEstimate,
    get_route_provider,
)


class TestGoogleMapsRouteProvider:
    """Tests for GoogleMapsRouteProvider.get_travel_time."""

    @pytest.fixture
    def provider(self):
        return GoogleMapsRouteProvider(api_key="test-api-key")

    def _directions_response(self, duration=1800, distance=25000, traffic_duration=None):
        """Build a minimal Google Directions API response."""
        leg = {
            "duration": {"value": duration, "text": f"{duration // 60} mins"},
            "distance": {"value": distance, "text": f"{distance / 1000} km"},
        }
        if traffic_duration is not None:
            leg["duration_in_traffic"] = {"value": traffic_duration, "text": ""}
        return {"status": "OK", "routes": [{"legs": [leg]}]}

    @pytest.mark.asyncio
    async def test_driving_returns_travel_estimate(self, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = self._directions_response(duration=1800, distance=25000)
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.route_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await provider.get_travel_time("Home St", "Office Ave", mode="driving")

        assert isinstance(result, TravelEstimate)
        assert result.duration_minutes == 30.0
        assert result.distance_km == 25.0
        assert result.origin == "Home St"
        assert result.destination == "Office Ave"
        assert result.mode == "driving"

    @pytest.mark.asyncio
    async def test_cycling_mode_maps_to_bicycling(self, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = self._directions_response(duration=2400, distance=12000)
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.route_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await provider.get_travel_time("A", "B", mode="cycling")

            # Verify "bicycling" was sent to Google, not "cycling"
            call_kwargs = mock_client.get.call_args
            params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
            assert params["mode"] == "bicycling"

    @pytest.mark.asyncio
    async def test_transit_mode_passed_as_is(self, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = self._directions_response()
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.route_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await provider.get_travel_time("A", "B", mode="transit")

            call_kwargs = mock_client.get.call_args
            params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
            assert params["mode"] == "transit"

    @pytest.mark.asyncio
    async def test_duration_in_traffic_preferred_over_duration(self, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = self._directions_response(
            duration=1800, distance=25000, traffic_duration=2400
        )
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.route_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await provider.get_travel_time("A", "B")

        # Should use traffic duration (2400s = 40min), not base (1800s = 30min)
        assert result.duration_minutes == 40.0

    @pytest.mark.asyncio
    async def test_no_route_raises_value_error(self, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ZERO_RESULTS", "routes": []}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.route_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="No route found"):
                await provider.get_travel_time("Nowhere", "Also Nowhere")

    @pytest.mark.asyncio
    async def test_api_key_included_in_params(self, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = self._directions_response()
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.route_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await provider.get_travel_time("A", "B")

            call_kwargs = mock_client.get.call_args
            params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
            assert params["key"] == "test-api-key"

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, provider):
        with patch("app.services.route_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.HTTPStatusError):
                await provider.get_travel_time("A", "B")


class TestGetRouteProvider:
    """Tests for the get_route_provider factory."""

    def test_returns_provider_when_api_key_set(self):
        settings = MagicMock()
        settings.google_maps_api_key.get_secret_value.return_value = "real-key"

        provider = get_route_provider(settings)

        assert isinstance(provider, GoogleMapsRouteProvider)

    def test_returns_none_when_api_key_empty(self):
        settings = MagicMock()
        settings.google_maps_api_key.get_secret_value.return_value = ""

        provider = get_route_provider(settings)

        assert provider is None

"""Unit tests for leave_time_tasks (calculate_leave_time, check_upcoming_events)."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.route_service import TravelEstimate
from app.tasks.leave_time_tasks import _calculate_and_notify, check_upcoming_events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_id():
    return str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))


@pytest.fixture
def event_id():
    return str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))


def _make_event(event_id, user_id, status="confirmed", location="Office", start_dt=None):
    """Build a mock ProposedEvent."""
    if start_dt is None:
        start_dt = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    event = MagicMock()
    event.id = event_id
    event.user_id = user_id
    event.status = status
    event.event_data = {
        "title": "Team Meeting",
        "start_datetime": start_dt,
        "location": location,
    }
    return event


def _make_preference(user_id, home_address="123 Home St", transport_mode="driving"):
    pref = MagicMock()
    pref.user_id = user_id
    pref.home_address = home_address
    pref.preferred_transport_mode = transport_mode
    return pref


def _make_device_token(user_id, platform="ios", token="device-token-abc"):
    dt = MagicMock()
    dt.user_id = user_id
    dt.platform = platform
    dt.token = token
    return dt


def _travel_estimate(**overrides):
    defaults = dict(
        origin="123 Home St",
        destination="Office",
        mode="driving",
        duration_minutes=30.0,
        distance_km=25.0,
        departure_time=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(overrides)
    return TravelEstimate(**defaults)


def _mock_db_with_results(event=None, pref=None, tokens=None):
    """Create a mock async DB session that returns the given objects.

    Successive calls to db.execute() return the objects in order:
      1st call -> event
      2nd call -> preference
      3rd call -> device tokens (list)
    """
    results = []
    for obj in [event, pref]:
        r = MagicMock()
        r.scalar_one_or_none.return_value = obj
        results.append(r)
    if tokens is not None:
        r = MagicMock()
        r.scalars.return_value.all.return_value = tokens
        results.append(r)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=results)
    return db


# ---------------------------------------------------------------------------
# _calculate_and_notify tests
# ---------------------------------------------------------------------------

class TestCalculateAndNotify:
    """Tests for the core _calculate_and_notify async function."""

    @pytest.mark.asyncio
    async def test_skips_when_no_route_provider(self, user_id, event_id):
        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=None), \
             patch("app.tasks.leave_time_tasks.get_settings"):
            await _calculate_and_notify(user_id, event_id)
            # Should return early without DB access — no errors

    @pytest.mark.asyncio
    async def test_skips_when_event_not_found(self, user_id, event_id):
        db = _mock_db_with_results(event=None)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=MagicMock()), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            # Only 1 DB call (event lookup), no further processing
            assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_when_event_not_confirmed(self, user_id, event_id):
        event = _make_event(event_id, user_id, status="proposed")
        db = _mock_db_with_results(event=event)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=MagicMock()), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_when_event_missing_location(self, user_id, event_id):
        event = _make_event(event_id, user_id, location=None)
        event.event_data = {"title": "Meeting", "start_datetime": datetime.now(timezone.utc).isoformat()}
        db = _mock_db_with_results(event=event)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=MagicMock()), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_when_event_missing_start_datetime(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        event.event_data = {"title": "Meeting", "location": "Office"}
        db = _mock_db_with_results(event=event)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=MagicMock()), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_when_invalid_start_datetime(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        event.event_data = {"title": "Meeting", "location": "Office", "start_datetime": "not-a-date"}
        db = _mock_db_with_results(event=event)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=MagicMock()), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_when_user_has_no_home_address(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id, home_address=None)
        db = _mock_db_with_results(event=event, pref=pref)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=MagicMock()), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            assert db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_when_no_preferences(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        db = _mock_db_with_results(event=event, pref=None)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=MagicMock()), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            assert db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_when_route_calculation_fails(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id)
        db = _mock_db_with_results(event=event, pref=pref)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        route_provider = AsyncMock()
        route_provider.get_travel_time.side_effect = Exception("API error")

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=route_provider), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory):
            await _calculate_and_notify(user_id, event_id)
            # Should not raise; error is caught and logged
            assert db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_when_no_device_tokens(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id)
        db = _mock_db_with_results(event=event, pref=pref, tokens=[])
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        route_provider = AsyncMock()
        route_provider.get_travel_time.return_value = _travel_estimate()

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=route_provider), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory), \
             patch("app.tasks.leave_time_tasks.get_push_service") as mock_push_svc:
            await _calculate_and_notify(user_id, event_id)
            mock_push_svc.return_value.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_notification_on_success(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id)
        token = _make_device_token(user_id, platform="ios", token="tok-123")
        db = _mock_db_with_results(event=event, pref=pref, tokens=[token])
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        route_provider = AsyncMock()
        route_provider.get_travel_time.return_value = _travel_estimate(duration_minutes=30.0, distance_km=25.0)

        mock_push = AsyncMock()

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=route_provider), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory), \
             patch("app.tasks.leave_time_tasks.get_push_service", return_value=mock_push):
            await _calculate_and_notify(user_id, event_id)

        mock_push.send.assert_called_once()
        call_kwargs = mock_push.send.call_args.kwargs
        assert call_kwargs["platform"] == "ios"
        assert call_kwargs["token"] == "tok-123"
        assert call_kwargs["title"] == "Time to Leave"
        assert "30 min" in call_kwargs["body"]
        assert "Team Meeting" in call_kwargs["body"]
        assert "25.0 km" in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_sends_to_multiple_devices(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id)
        tokens = [
            _make_device_token(user_id, platform="ios", token="tok-ios"),
            _make_device_token(user_id, platform="android", token="tok-android"),
        ]
        db = _mock_db_with_results(event=event, pref=pref, tokens=tokens)
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        route_provider = AsyncMock()
        route_provider.get_travel_time.return_value = _travel_estimate()

        mock_push = AsyncMock()

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=route_provider), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory), \
             patch("app.tasks.leave_time_tasks.get_push_service", return_value=mock_push):
            await _calculate_and_notify(user_id, event_id)

        assert mock_push.send.call_count == 2

    @pytest.mark.asyncio
    async def test_uses_preferred_transport_mode(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id, transport_mode="transit")
        token = _make_device_token(user_id)
        db = _mock_db_with_results(event=event, pref=pref, tokens=[token])
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        route_provider = AsyncMock()
        route_provider.get_travel_time.return_value = _travel_estimate(mode="transit")

        mock_push = AsyncMock()

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=route_provider), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory), \
             patch("app.tasks.leave_time_tasks.get_push_service", return_value=mock_push):
            await _calculate_and_notify(user_id, event_id)

        route_provider.get_travel_time.assert_called_once_with(
            origin="123 Home St",
            destination="Office",
            mode="transit",
        )

    @pytest.mark.asyncio
    async def test_defaults_to_driving_when_no_transport_mode(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id, transport_mode=None)
        token = _make_device_token(user_id)
        db = _mock_db_with_results(event=event, pref=pref, tokens=[token])
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        route_provider = AsyncMock()
        route_provider.get_travel_time.return_value = _travel_estimate()

        mock_push = AsyncMock()

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=route_provider), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory), \
             patch("app.tasks.leave_time_tasks.get_push_service", return_value=mock_push):
            await _calculate_and_notify(user_id, event_id)

        route_provider.get_travel_time.assert_called_once_with(
            origin="123 Home St",
            destination="Office",
            mode="driving",
        )

    @pytest.mark.asyncio
    async def test_notification_extra_data_includes_event_id_and_travel_info(self, user_id, event_id):
        event = _make_event(event_id, user_id)
        pref = _make_preference(user_id)
        token = _make_device_token(user_id)
        db = _mock_db_with_results(event=event, pref=pref, tokens=[token])
        session_factory = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=db), __aexit__=AsyncMock(return_value=False)))

        route_provider = AsyncMock()
        route_provider.get_travel_time.return_value = _travel_estimate(duration_minutes=45.0)

        mock_push = AsyncMock()

        with patch("app.tasks.leave_time_tasks.get_route_provider", return_value=route_provider), \
             patch("app.tasks.leave_time_tasks.get_settings"), \
             patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory), \
             patch("app.tasks.leave_time_tasks.get_push_service", return_value=mock_push):
            await _calculate_and_notify(user_id, event_id)

        call_kwargs = mock_push.send.call_args.kwargs
        extra = call_kwargs["extra_data"]
        assert extra["event_id"] == event_id
        assert extra["travel_minutes"] == "45"
        assert "departure_time" in extra


# ---------------------------------------------------------------------------
# check_upcoming_events tests
# ---------------------------------------------------------------------------

def _run_check_upcoming(mock_events):
    """Helper: run check_upcoming_events synchronously with mocked DB.

    These tests are sync (no @pytest.mark.asyncio) so asyncio.run() inside
    the Celery task works without conflicting with an already-running loop.
    """
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = mock_events
    db.execute = AsyncMock(return_value=result)

    session_factory = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=db),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch("app.tasks.leave_time_tasks._get_async_session", return_value=session_factory), \
         patch("app.tasks.leave_time_tasks.calculate_leave_time") as mock_task:
        mock_task.delay = MagicMock()
        check_upcoming_events.__wrapped__()
        return mock_task


class TestCheckUpcomingEvents:
    """Tests for the periodic check_upcoming_events task."""

    def test_enqueues_tasks_for_events_within_window(self):
        now = datetime.now(timezone.utc)
        future_event = _make_event(
            "evt-1", "user-1",
            start_dt=(now + timedelta(hours=1)).isoformat(),
        )

        mock_task = _run_check_upcoming([future_event])

        mock_task.delay.assert_called_once_with(
            user_id=str(future_event.user_id),
            event_id=str(future_event.id),
        )

    def test_skips_events_outside_window(self):
        now = datetime.now(timezone.utc)
        far_future_event = _make_event(
            "evt-far", "user-1",
            start_dt=(now + timedelta(hours=5)).isoformat(),
        )

        mock_task = _run_check_upcoming([far_future_event])
        mock_task.delay.assert_not_called()

    def test_skips_events_with_invalid_start_datetime(self):
        bad_event = _make_event("evt-bad", "user-1")
        bad_event.event_data = {"start_datetime": "not-a-date", "location": "X"}

        mock_task = _run_check_upcoming([bad_event])
        mock_task.delay.assert_not_called()

    def test_skips_events_missing_start_datetime(self):
        event = _make_event("evt-no-start", "user-1")
        event.event_data = {"location": "Somewhere"}

        mock_task = _run_check_upcoming([event])
        mock_task.delay.assert_not_called()

    def test_skips_past_events(self):
        now = datetime.now(timezone.utc)
        past_event = _make_event(
            "evt-past", "user-1",
            start_dt=(now - timedelta(hours=1)).isoformat(),
        )

        mock_task = _run_check_upcoming([past_event])
        mock_task.delay.assert_not_called()

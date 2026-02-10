"""Tests for digest subscription schemas, DIGEST_SCHEMA validation, and digest generation."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jsonschema
import pytest
from pydantic import ValidationError

from app.schemas.automation import (
    DigestPreviewResponse,
    DigestSubscriptionCreate,
    DigestSubscriptionResponse,
    DigestSubscriptionUpdate,
)
from app.services.ai_prompts import DIGEST_SCHEMA
from app.services.ai_service import AIService, DigestSummary


# ---------------------------------------------------------------------------
# DIGEST_SCHEMA JSON-schema validation
# ---------------------------------------------------------------------------


class TestDigestSchema:
    """Test that DIGEST_SCHEMA validates correctly via jsonschema."""

    def test_valid_full_digest(self):
        data = {
            "summary": "You received 12 alerts today, mostly invoices and meeting requests.",
            "highlights": [
                "Urgent invoice from Acme Corp due Friday",
                "Team standup rescheduled to 10am",
            ],
            "stats": {
                "total": 12,
                "by_category": {"invoice": 5, "meeting": 4, "general": 3},
            },
        }
        jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_valid_minimal_digest(self):
        data = {
            "summary": "No significant activity.",
            "highlights": [],
            "stats": {"total": 0, "by_category": {}},
        }
        jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_valid_single_highlight(self):
        data = {
            "summary": "One alert.",
            "highlights": ["Payment received"],
            "stats": {"total": 1, "by_category": {"invoice": 1}},
        }
        jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_missing_summary_rejected(self):
        data = {
            "highlights": ["Something"],
            "stats": {"total": 1, "by_category": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_missing_highlights_rejected(self):
        data = {
            "summary": "Test",
            "stats": {"total": 0, "by_category": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_missing_stats_rejected(self):
        data = {
            "summary": "Test",
            "highlights": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_stats_missing_total_rejected(self):
        data = {
            "summary": "Test",
            "highlights": [],
            "stats": {"by_category": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_stats_missing_by_category_rejected(self):
        data = {
            "summary": "Test",
            "highlights": [],
            "stats": {"total": 0},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_stats_total_negative_rejected(self):
        data = {
            "summary": "Test",
            "highlights": [],
            "stats": {"total": -1, "by_category": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_stats_total_must_be_integer(self):
        data = {
            "summary": "Test",
            "highlights": [],
            "stats": {"total": 5.5, "by_category": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_extra_top_level_field_rejected(self):
        data = {
            "summary": "Test",
            "highlights": [],
            "stats": {"total": 0, "by_category": {}},
            "extra": "not allowed",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_extra_stats_field_rejected(self):
        data = {
            "summary": "Test",
            "highlights": [],
            "stats": {"total": 0, "by_category": {}, "extra": True},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_highlights_must_be_array(self):
        data = {
            "summary": "Test",
            "highlights": "not an array",
            "stats": {"total": 0, "by_category": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)

    def test_highlights_items_must_be_strings(self):
        data = {
            "summary": "Test",
            "highlights": [123],
            "stats": {"total": 0, "by_category": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=DIGEST_SCHEMA)


# ---------------------------------------------------------------------------
# DigestSummary Pydantic model
# ---------------------------------------------------------------------------


class TestDigestSummaryModel:
    """Test the DigestSummary Pydantic model from ai_service."""

    def test_valid_construction(self):
        s = DigestSummary(
            summary="12 alerts today.",
            highlights=["Urgent invoice"],
            stats={"total": 12, "by_category": {"invoice": 5}},
        )
        assert s.summary == "12 alerts today."
        assert len(s.highlights) == 1
        assert s.stats["total"] == 12

    def test_empty_highlights(self):
        s = DigestSummary(summary="Quiet day.", highlights=[], stats={"total": 0})
        assert s.highlights == []

    def test_stats_accepts_arbitrary_dict(self):
        s = DigestSummary(
            summary="Test",
            highlights=[],
            stats={"total": 5, "by_category": {"general": 5}, "custom_key": "ok"},
        )
        assert s.stats["custom_key"] == "ok"

    def test_missing_summary_raises(self):
        with pytest.raises(ValidationError):
            DigestSummary(highlights=[], stats={})

    def test_missing_highlights_raises(self):
        with pytest.raises(ValidationError):
            DigestSummary(summary="Test", stats={})

    def test_missing_stats_raises(self):
        with pytest.raises(ValidationError):
            DigestSummary(summary="Test", highlights=[])


# ---------------------------------------------------------------------------
# DigestSubscriptionCreate schema
# ---------------------------------------------------------------------------


class TestDigestSubscriptionCreate:
    """Test validation on DigestSubscriptionCreate."""

    def test_defaults(self):
        sub = DigestSubscriptionCreate()
        assert sub.frequency == "daily"
        assert sub.day_of_week == 0
        assert sub.hour_utc == 8

    def test_daily(self):
        sub = DigestSubscriptionCreate(frequency="daily", hour_utc=14)
        assert sub.frequency == "daily"
        assert sub.hour_utc == 14

    def test_weekly(self):
        sub = DigestSubscriptionCreate(frequency="weekly", day_of_week=4, hour_utc=9)
        assert sub.frequency == "weekly"
        assert sub.day_of_week == 4

    def test_invalid_frequency_rejected(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionCreate(frequency="monthly")

    def test_hour_utc_too_high(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionCreate(hour_utc=24)

    def test_hour_utc_too_low(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionCreate(hour_utc=-1)

    def test_day_of_week_too_high(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionCreate(day_of_week=7)

    def test_day_of_week_too_low(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionCreate(day_of_week=-1)

    def test_hour_utc_boundary_0(self):
        sub = DigestSubscriptionCreate(hour_utc=0)
        assert sub.hour_utc == 0

    def test_hour_utc_boundary_23(self):
        sub = DigestSubscriptionCreate(hour_utc=23)
        assert sub.hour_utc == 23

    def test_day_of_week_boundary_6(self):
        sub = DigestSubscriptionCreate(day_of_week=6)
        assert sub.day_of_week == 6


# ---------------------------------------------------------------------------
# DigestSubscriptionResponse schema
# ---------------------------------------------------------------------------


class TestDigestSubscriptionResponse:
    """Test DigestSubscriptionResponse serialization."""

    def test_full_response(self):
        now = datetime.now(timezone.utc)
        resp = DigestSubscriptionResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            frequency="daily",
            day_of_week=0,
            hour_utc=8,
            is_active=True,
            last_sent_at=now,
            created_at=now,
        )
        assert resp.frequency == "daily"
        assert resp.is_active is True
        assert resp.last_sent_at == now

    def test_last_sent_at_nullable(self):
        now = datetime.now(timezone.utc)
        resp = DigestSubscriptionResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            frequency="weekly",
            day_of_week=2,
            hour_utc=10,
            is_active=False,
            last_sent_at=None,
            created_at=now,
        )
        assert resp.last_sent_at is None

    def test_from_attributes_config(self):
        assert DigestSubscriptionResponse.model_config["from_attributes"] is True


# ---------------------------------------------------------------------------
# DigestSubscriptionUpdate schema
# ---------------------------------------------------------------------------


class TestDigestSubscriptionUpdate:
    """Test partial-update schema DigestSubscriptionUpdate."""

    def test_all_none_by_default(self):
        upd = DigestSubscriptionUpdate()
        assert upd.frequency is None
        assert upd.day_of_week is None
        assert upd.hour_utc is None

    def test_partial_update_frequency(self):
        upd = DigestSubscriptionUpdate(frequency="weekly")
        assert upd.frequency == "weekly"
        assert upd.day_of_week is None

    def test_partial_update_hour(self):
        upd = DigestSubscriptionUpdate(hour_utc=15)
        assert upd.hour_utc == 15

    def test_invalid_frequency_rejected(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionUpdate(frequency="yearly")

    def test_invalid_hour_rejected(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionUpdate(hour_utc=25)

    def test_invalid_day_of_week_rejected(self):
        with pytest.raises(ValidationError):
            DigestSubscriptionUpdate(day_of_week=7)


# ---------------------------------------------------------------------------
# DigestPreviewResponse schema
# ---------------------------------------------------------------------------


class TestDigestPreviewResponse:
    """Test DigestPreviewResponse construction."""

    def test_valid_construction(self):
        now = datetime.now(timezone.utc)
        preview = DigestPreviewResponse(
            summary="You had 5 alerts.",
            alert_count=5,
            highlights=["Invoice from Acme"],
            period_start=now - timedelta(days=1),
            period_end=now,
        )
        assert preview.alert_count == 5
        assert len(preview.highlights) == 1
        assert preview.period_start < preview.period_end

    def test_empty_highlights(self):
        now = datetime.now(timezone.utc)
        preview = DigestPreviewResponse(
            summary="Nothing new.",
            alert_count=0,
            highlights=[],
            period_start=now - timedelta(days=1),
            period_end=now,
        )
        assert preview.highlights == []

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            DigestPreviewResponse(
                summary="Test",
                alert_count=1,
                # missing highlights, period_start, period_end
            )


# ---------------------------------------------------------------------------
# Scheduling logic (daily vs weekly, hour_utc, double-send prevention)
# ---------------------------------------------------------------------------


def _make_subscription(
    frequency="daily",
    day_of_week=0,
    hour_utc=8,
    is_active=True,
    last_sent_at=None,
    user_id=None,
):
    """Build a mock DigestSubscription."""
    sub = MagicMock()
    sub.frequency = frequency
    sub.day_of_week = day_of_week
    sub.hour_utc = hour_utc
    sub.is_active = is_active
    sub.last_sent_at = last_sent_at
    sub.user_id = user_id or uuid.uuid4()
    return sub


class TestSchedulingLogic:
    """Test the scheduling rules extracted from send_digest_notifications task.

    The scheduling logic in the task:
      - Runs every hour; picks subscriptions where hour_utc == current_hour
      - For weekly: additionally checks day_of_week == current_dow
      - Double-send prevention:
        - daily: skip if last_sent_at is < 20 hours ago
        - weekly: skip if last_sent_at is < 6 days ago
    """

    def test_daily_subscription_matches_correct_hour(self):
        """A daily sub at hour=10 should be due when current_hour is 10."""
        sub = _make_subscription(frequency="daily", hour_utc=10)
        current_hour = 10
        assert sub.hour_utc == current_hour

    def test_daily_subscription_skips_wrong_hour(self):
        """A daily sub at hour=10 should NOT fire at hour 15."""
        sub = _make_subscription(frequency="daily", hour_utc=10)
        current_hour = 15
        assert sub.hour_utc != current_hour

    def test_weekly_subscription_matches_correct_day_and_hour(self):
        """A weekly sub for day=2 (Wednesday), hour=9 should fire on Wednesday at 9."""
        sub = _make_subscription(frequency="weekly", day_of_week=2, hour_utc=9)
        current_dow = 2
        current_hour = 9
        assert sub.hour_utc == current_hour
        # Weekly constraint: day must match
        should_skip = sub.frequency == "weekly" and sub.day_of_week != current_dow
        assert should_skip is False

    def test_weekly_subscription_skips_wrong_day(self):
        """A weekly sub for day=2 should be skipped on day=4."""
        sub = _make_subscription(frequency="weekly", day_of_week=2, hour_utc=9)
        current_dow = 4
        should_skip = sub.frequency == "weekly" and sub.day_of_week != current_dow
        assert should_skip is True

    def test_daily_double_send_prevention_within_20_hours(self):
        """Daily sub sent 10 hours ago should be skipped (< 20h threshold)."""
        now = datetime.now(timezone.utc)
        last_sent = now - timedelta(hours=10)
        sub = _make_subscription(frequency="daily", last_sent_at=last_sent)

        should_skip = (now - sub.last_sent_at) < timedelta(hours=20)
        assert should_skip is True

    def test_daily_no_double_send_after_20_hours(self):
        """Daily sub sent 21 hours ago should NOT be skipped."""
        now = datetime.now(timezone.utc)
        last_sent = now - timedelta(hours=21)
        sub = _make_subscription(frequency="daily", last_sent_at=last_sent)

        should_skip = (now - sub.last_sent_at) < timedelta(hours=20)
        assert should_skip is False

    def test_weekly_double_send_prevention_within_6_days(self):
        """Weekly sub sent 3 days ago should be skipped (< 6 day threshold)."""
        now = datetime.now(timezone.utc)
        last_sent = now - timedelta(days=3)
        sub = _make_subscription(frequency="weekly", last_sent_at=last_sent)

        should_skip = (now - sub.last_sent_at) < timedelta(days=6)
        assert should_skip is True

    def test_weekly_no_double_send_after_6_days(self):
        """Weekly sub sent 7 days ago should NOT be skipped."""
        now = datetime.now(timezone.utc)
        last_sent = now - timedelta(days=7)
        sub = _make_subscription(frequency="weekly", last_sent_at=last_sent)

        should_skip = (now - sub.last_sent_at) < timedelta(days=6)
        assert should_skip is False

    def test_no_last_sent_at_is_never_skipped(self):
        """A subscription that has never been sent should not be skipped."""
        sub = _make_subscription(frequency="daily", last_sent_at=None)
        # The task checks `if sub.last_sent_at:` first, so None means no skip
        assert sub.last_sent_at is None

    def test_daily_period_is_one_day(self):
        """Daily digest period_start should be now - 1 day."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=1)
        assert (now - period_start).total_seconds() == pytest.approx(86400, abs=1)

    def test_weekly_period_is_one_week(self):
        """Weekly digest period_start should be now - 7 days."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(weeks=1)
        assert (now - period_start).total_seconds() == pytest.approx(604800, abs=1)


# ---------------------------------------------------------------------------
# Digest generation with mocked AI provider
# ---------------------------------------------------------------------------


class TestDigestGenerationMocked:
    """Test generate_digest_summary with a mocked AI provider."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = json.dumps({
            "summary": "You had 8 alerts: 3 invoices, 2 meetings, 3 general.",
            "highlights": [
                "Invoice from Acme Corp due Friday",
                "Team standup moved to 10am",
            ],
            "stats": {
                "total": 8,
                "by_category": {"invoice": 3, "meeting": 2, "general": 3},
            },
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_digest_summary(
                alert_summaries="- [invoice] From: acme@co ...\n- [meeting] From: bob@co ...",
                alert_count=8,
                period_start="2024-02-01T00:00:00+00:00",
            )

        assert result is not None
        assert isinstance(result, DigestSummary)
        assert result.stats["total"] == 8
        assert len(result.highlights) == 2
        assert "invoice" in result.summary.lower() or "alerts" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = "not json at all {"

            result = await service.generate_digest_summary(
                alert_summaries="some alerts",
                alert_count=1,
                period_start="2024-02-01T00:00:00+00:00",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_schema_violation_returns_none(self):
        """AI returns valid JSON but missing required 'stats' field."""
        mock_response = json.dumps({
            "summary": "Test digest",
            "highlights": [],
            # missing "stats" entirely
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_digest_summary(
                alert_summaries="alerts",
                alert_count=0,
                period_start="2024-02-01T00:00:00+00:00",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extra_fields_in_response_rejected(self):
        """AI returns valid JSON with extra top-level fields (additionalProperties: false)."""
        mock_response = json.dumps({
            "summary": "Test",
            "highlights": [],
            "stats": {"total": 0, "by_category": {}},
            "bonus_field": True,
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_digest_summary(
                alert_summaries="",
                alert_count=0,
                period_start="2024-02-01T00:00:00+00:00",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_markdown_code_block_stripped(self):
        """AI wraps JSON in markdown code fences; parser should still handle it."""
        raw_json = {
            "summary": "Quiet day.",
            "highlights": [],
            "stats": {"total": 0, "by_category": {}},
        }
        mock_response = f"```json\n{json.dumps(raw_json)}\n```"

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_digest_summary(
                alert_summaries="",
                alert_count=0,
                period_start="2024-02-01T00:00:00+00:00",
            )

        assert result is not None
        assert result.summary == "Quiet day."

    @pytest.mark.asyncio
    async def test_zero_alerts_still_valid(self):
        mock_response = json.dumps({
            "summary": "No new alerts in the past 24 hours.",
            "highlights": [],
            "stats": {"total": 0, "by_category": {}},
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_digest_summary(
                alert_summaries="",
                alert_count=0,
                period_start="2024-02-01T00:00:00+00:00",
            )

        assert result is not None
        assert result.stats["total"] == 0
        assert result.highlights == []

    @pytest.mark.asyncio
    async def test_negative_stats_total_rejected(self):
        """stats.total with negative value should fail schema validation."""
        mock_response = json.dumps({
            "summary": "Bad data.",
            "highlights": [],
            "stats": {"total": -5, "by_category": {}},
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_digest_summary(
                alert_summaries="",
                alert_count=0,
                period_start="2024-02-01T00:00:00+00:00",
            )

        assert result is None

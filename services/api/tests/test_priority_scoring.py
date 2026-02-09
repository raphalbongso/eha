"""Tests for heuristic priority inbox scoring."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.services.priority_service import compute_heuristic_priority


@dataclass
class FakeMessage:
    """Minimal stand-in for ProcessedMessage."""

    message_id: str = "msg_001"
    subject: str | None = "Test Subject"
    from_addr: str | None = "alice@company.com"
    snippet: str | None = "Some snippet text"
    has_attachment: bool = False
    label_ids: str | None = "INBOX"
    received_at: datetime | None = None
    thread_id: str | None = None


class TestBaselineScoring:
    def test_baseline_score(self):
        msg = FakeMessage()
        result = compute_heuristic_priority(msg)
        assert result["score"] == 50
        assert isinstance(result["signals"], list)

    def test_score_bounds_clamped_low(self):
        """Score should never go below 0 even with many negative signals."""
        msg = FakeMessage(
            subject="Unsubscribe from newsletter digest",
            from_addr="noreply@spam.com",
            label_ids="INBOX,SPAM,CATEGORY_PROMOTIONS",
        )
        result = compute_heuristic_priority(msg)
        assert result["score"] >= 0

    def test_score_bounds_clamped_high(self):
        """Score should never exceed 100 even with many positive signals."""
        msg = FakeMessage(
            subject="URGENT: Action Required ASAP deadline",
            label_ids="INBOX,IMPORTANT,STARRED",
            has_attachment=True,
            received_at=datetime.now(timezone.utc),
        )
        result = compute_heuristic_priority(msg)
        assert result["score"] <= 100


class TestLabelSignals:
    def test_important_label_boosts_score(self):
        msg = FakeMessage(label_ids="INBOX,IMPORTANT")
        result = compute_heuristic_priority(msg)
        assert result["score"] > 50
        assert "marked important by Gmail" in result["signals"]

    def test_starred_boosts_score(self):
        msg = FakeMessage(label_ids="INBOX,STARRED")
        result = compute_heuristic_priority(msg)
        assert result["score"] > 50
        assert "starred" in result["signals"]

    def test_promotions_lowers_score(self):
        msg = FakeMessage(label_ids="INBOX,CATEGORY_PROMOTIONS")
        result = compute_heuristic_priority(msg)
        assert result["score"] < 50
        assert "promotional or social" in result["signals"]

    def test_spam_label_lowers_score(self):
        msg = FakeMessage(label_ids="SPAM")
        result = compute_heuristic_priority(msg)
        assert result["score"] < 50
        assert "spam" in result["signals"]


class TestKeywordSignals:
    def test_urgent_keyword_boosts_score(self):
        msg = FakeMessage(subject="URGENT: Server down")
        result = compute_heuristic_priority(msg)
        assert result["score"] > 50
        assert "contains urgent keywords" in result["signals"]

    def test_asap_keyword_boosts_score(self):
        msg = FakeMessage(snippet="Please respond ASAP")
        result = compute_heuristic_priority(msg)
        assert result["score"] > 50

    def test_newsletter_keyword_lowers_score(self):
        msg = FakeMessage(subject="Weekly Newsletter")
        result = compute_heuristic_priority(msg)
        assert result["score"] < 50
        assert "contains low-priority keywords" in result["signals"]

    def test_unsubscribe_in_snippet(self):
        msg = FakeMessage(snippet="Click to unsubscribe from this list")
        result = compute_heuristic_priority(msg)
        assert result["score"] < 50


class TestSenderSignals:
    def test_noreply_lowers_score(self):
        msg = FakeMessage(from_addr="noreply@example.com")
        result = compute_heuristic_priority(msg)
        assert result["score"] < 50
        assert "sent from no-reply address" in result["signals"]

    def test_no_reply_with_hyphen(self):
        msg = FakeMessage(from_addr="no-reply@example.com")
        result = compute_heuristic_priority(msg)
        assert "sent from no-reply address" in result["signals"]


class TestAttachmentSignal:
    def test_attachment_boosts_score(self):
        msg = FakeMessage(has_attachment=True)
        result = compute_heuristic_priority(msg)
        assert result["score"] > 50
        assert "has attachment" in result["signals"]


class TestRecencySignals:
    def test_recent_message_boosts_score(self):
        msg = FakeMessage(received_at=datetime.now(timezone.utc) - timedelta(minutes=30))
        result = compute_heuristic_priority(msg)
        assert result["score"] > 50
        assert "received within last hour" in result["signals"]

    def test_few_hours_old_slight_boost(self):
        msg = FakeMessage(received_at=datetime.now(timezone.utc) - timedelta(hours=3))
        result = compute_heuristic_priority(msg)
        assert result["score"] > 50
        assert "received within last 6 hours" in result["signals"]

    def test_old_message_lowers_score(self):
        msg = FakeMessage(received_at=datetime.now(timezone.utc) - timedelta(days=5))
        result = compute_heuristic_priority(msg)
        assert result["score"] < 50
        assert "older than 3 days" in result["signals"]


class TestNullFieldHandling:
    def test_all_null_fields(self):
        msg = FakeMessage(
            subject=None,
            from_addr=None,
            snippet=None,
            label_ids=None,
            received_at=None,
        )
        result = compute_heuristic_priority(msg)
        assert result["score"] == 50
        assert result["signals"] == []

    def test_empty_string_fields(self):
        msg = FakeMessage(subject="", from_addr="", snippet="", label_ids="")
        result = compute_heuristic_priority(msg)
        assert result["score"] == 50

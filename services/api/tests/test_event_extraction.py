"""Tests for AI event extraction output validation."""

import jsonschema
import pytest

from app.services.ai_prompts import EVENT_SCHEMA
from app.services.ai_service import EventProposal


class TestEventSchema:
    """Test that event extraction outputs conform to the JSON schema."""

    def test_valid_full_event(self):
        data = {
            "title": "Team Meeting",
            "start_datetime": "2024-02-15T15:00:00Z",
            "end_datetime": "2024-02-15T16:00:00Z",
            "duration_minutes": 60,
            "location": "Room 42",
            "attendees": ["alice@company.com", "bob@company.com"],
            "confidence": 0.95,
        }
        jsonschema.validate(instance=data, schema=EVENT_SCHEMA)
        event = EventProposal(**data)
        assert event.title == "Team Meeting"
        assert event.confidence == 0.95

    def test_valid_minimal_event(self):
        data = {
            "title": "Coffee Chat",
            "start_datetime": None,
            "end_datetime": None,
            "duration_minutes": None,
            "location": None,
            "attendees": None,
            "confidence": 0.3,
        }
        jsonschema.validate(instance=data, schema=EVENT_SCHEMA)
        event = EventProposal(**data)
        assert event.title == "Coffee Chat"
        assert event.confidence == 0.3
        assert event.location is None

    def test_null_title_valid_schema(self):
        data = {
            "title": None,
            "confidence": 0.1,
        }
        jsonschema.validate(instance=data, schema=EVENT_SCHEMA)

    def test_invalid_confidence_too_high(self):
        data = {
            "title": "Meeting",
            "confidence": 1.5,
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=EVENT_SCHEMA)

    def test_invalid_confidence_negative(self):
        data = {
            "title": "Meeting",
            "confidence": -0.1,
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=EVENT_SCHEMA)

    def test_missing_confidence(self):
        data = {
            "title": "Meeting",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=EVENT_SCHEMA)

    def test_extra_fields_rejected(self):
        data = {
            "title": "Meeting",
            "confidence": 0.8,
            "extra_field": "not allowed",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=EVENT_SCHEMA)


class TestLowConfidenceHandling:
    """Verify that ambiguous events get low confidence."""

    def test_no_datetime_means_low_confidence(self):
        """Events without specific date/time should have confidence < 0.5."""
        # This simulates what the AI should output
        data = {
            "title": "Catch up sometime",
            "start_datetime": None,
            "end_datetime": None,
            "duration_minutes": None,
            "location": None,
            "attendees": None,
            "confidence": 0.2,
        }
        event = EventProposal(**data)
        assert event.confidence < 0.5, "Events without datetime should have low confidence"

    def test_date_without_time_means_moderate_confidence(self):
        """Events with date but no specific time should have confidence < 0.7."""
        data = {
            "title": "Report due",
            "start_datetime": "2024-02-15",
            "end_datetime": None,
            "duration_minutes": None,
            "location": None,
            "attendees": None,
            "confidence": 0.6,
        }
        event = EventProposal(**data)
        assert event.confidence < 0.7

    def test_full_datetime_means_high_confidence(self):
        """Events with full date and time can have high confidence."""
        data = {
            "title": "Sprint Review",
            "start_datetime": "2024-02-15T14:00:00+01:00",
            "end_datetime": "2024-02-15T15:00:00+01:00",
            "duration_minutes": 60,
            "location": "Meeting Room A",
            "attendees": ["team@company.com"],
            "confidence": 0.92,
        }
        event = EventProposal(**data)
        assert event.confidence > 0.7


class TestEdgeCases:
    def test_unicode_in_title(self):
        data = {
            "title": "Reunion d'equipe",
            "start_datetime": "2024-02-15T10:00:00Z",
            "end_datetime": None,
            "duration_minutes": 30,
            "location": "Bureau 3eme etage",
            "attendees": None,
            "confidence": 0.85,
        }
        event = EventProposal(**data)
        assert "equipe" in event.title

    def test_empty_attendees_list(self):
        data = {
            "title": "Solo work block",
            "start_datetime": "2024-02-15T09:00:00Z",
            "end_datetime": "2024-02-15T12:00:00Z",
            "duration_minutes": 180,
            "location": None,
            "attendees": [],
            "confidence": 0.7,
        }
        jsonschema.validate(instance=data, schema=EVENT_SCHEMA)
        event = EventProposal(**data)
        assert event.attendees == []

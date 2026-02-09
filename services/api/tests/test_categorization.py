"""Tests for email categorization and enhanced summarization."""

import jsonschema
import pytest

from app.services.ai_prompts import SUMMARY_SCHEMA
from app.services.ai_service import Summary


class TestSummarySchema:
    """Test that the extended summary schema validates correctly."""

    def test_valid_full_summary(self):
        data = {
            "summary": "Alice sent an invoice for Q4 services.",
            "action_items": ["Review and approve invoice"],
            "urgency": "medium",
            "category": "invoice",
            "priority_score": 72,
            "priority_signals": ["contains deadline", "requires response"],
        }
        jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)
        s = Summary(**data)
        assert s.category == "invoice"
        assert s.priority_score == 72
        assert len(s.priority_signals) == 2

    def test_valid_minimal_summary(self):
        data = {
            "summary": "A general email.",
            "action_items": [],
            "urgency": "low",
            "category": "general",
            "priority_score": 10,
            "priority_signals": [],
        }
        jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)

    def test_all_category_values(self):
        categories = [
            "general",
            "invoice",
            "meeting",
            "newsletter",
            "action_required",
            "shipping",
            "security",
        ]
        for cat in categories:
            data = {
                "summary": "Test",
                "action_items": [],
                "urgency": "low",
                "category": cat,
                "priority_score": 50,
                "priority_signals": [],
            }
            jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)

    def test_invalid_category_rejected(self):
        data = {
            "summary": "Test",
            "action_items": [],
            "urgency": "low",
            "category": "spam",
            "priority_score": 50,
            "priority_signals": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)

    def test_priority_score_too_high(self):
        data = {
            "summary": "Test",
            "action_items": [],
            "urgency": "low",
            "category": "general",
            "priority_score": 150,
            "priority_signals": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)

    def test_priority_score_negative(self):
        data = {
            "summary": "Test",
            "action_items": [],
            "urgency": "low",
            "category": "general",
            "priority_score": -1,
            "priority_signals": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)

    def test_priority_score_must_be_integer(self):
        data = {
            "summary": "Test",
            "action_items": [],
            "urgency": "low",
            "category": "general",
            "priority_score": 50.5,
            "priority_signals": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)

    def test_missing_category_rejected(self):
        data = {
            "summary": "Test",
            "action_items": [],
            "urgency": "low",
            "priority_score": 50,
            "priority_signals": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)

    def test_extra_fields_rejected(self):
        data = {
            "summary": "Test",
            "action_items": [],
            "urgency": "low",
            "category": "general",
            "priority_score": 50,
            "priority_signals": [],
            "extra": "not allowed",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=SUMMARY_SCHEMA)


class TestSummaryModelDefaults:
    """Test backward compat defaults on the Summary Pydantic model."""

    def test_defaults_applied(self):
        s = Summary(summary="Test", action_items=[], urgency="low")
        assert s.category == "general"
        assert s.priority_score == 50
        assert s.priority_signals == []

    def test_full_fields(self):
        s = Summary(
            summary="Invoice from vendor",
            action_items=["pay"],
            urgency="high",
            category="invoice",
            priority_score=90,
            priority_signals=["contains deadline"],
        )
        assert s.category == "invoice"
        assert s.priority_score == 90

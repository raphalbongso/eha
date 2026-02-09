"""Tests for smart reply suggestions (style-aware drafts)."""

import json
from unittest.mock import AsyncMock, patch

import jsonschema
import pytest

from app.services.ai_prompts import STYLE_DRAFT_SCHEMA
from app.services.ai_service import AIService, DetectedStyle, StyleAwareDraftResponse


class TestStyleDraftSchema:
    """Test the style-aware draft JSON schema validation."""

    def test_valid_full_response(self):
        data = {
            "detected_style": {
                "formality": "casual",
                "avg_length": "short",
                "greeting_style": "Hey",
                "sign_off_style": "Cheers",
                "traits": ["uses contractions", "emoji usage"],
            },
            "drafts": [
                {"tone": "friendly", "subject": "Re: Hello", "body": "Hey! Sounds good."},
            ],
        }
        jsonschema.validate(instance=data, schema=STYLE_DRAFT_SCHEMA)

    def test_all_formality_values(self):
        for f in ["casual", "neutral", "formal"]:
            data = {
                "detected_style": {
                    "formality": f,
                    "avg_length": "medium",
                    "greeting_style": "Hi",
                    "sign_off_style": "Best",
                    "traits": [],
                },
                "drafts": [
                    {"tone": "formal", "subject": "Re: Test", "body": "Hello."},
                ],
            }
            jsonschema.validate(instance=data, schema=STYLE_DRAFT_SCHEMA)

    def test_invalid_formality(self):
        data = {
            "detected_style": {
                "formality": "super_casual",
                "avg_length": "medium",
                "greeting_style": "Hi",
                "sign_off_style": "Best",
                "traits": [],
            },
            "drafts": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=STYLE_DRAFT_SCHEMA)

    def test_missing_detected_style(self):
        data = {
            "drafts": [{"tone": "formal", "subject": "Re: Test", "body": "Hello."}],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=STYLE_DRAFT_SCHEMA)

    def test_extra_fields_in_style_rejected(self):
        data = {
            "detected_style": {
                "formality": "casual",
                "avg_length": "short",
                "greeting_style": "Hey",
                "sign_off_style": "Cheers",
                "traits": [],
                "extra": "nope",
            },
            "drafts": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=STYLE_DRAFT_SCHEMA)


class TestFormatSentSamples:
    """Test the _format_sent_samples static helper."""

    def test_with_samples(self):
        samples = [
            {"to_addr": "bob@co.com", "subject": "Re: Plans", "body": "Sounds good!"},
            {"to_addr": "charlie@co.com", "subject": "Update", "body": "Here's the update."},
        ]
        result = AIService._format_sent_samples(samples)
        assert "[Sent Email 1]" in result
        assert "[Sent Email 2]" in result
        assert "bob@co.com" in result

    def test_empty_samples_fallback(self):
        result = AIService._format_sent_samples([])
        assert "no sent email samples" in result.lower()

    def test_missing_fields_use_defaults(self):
        samples = [{"body": "Just a body"}]
        result = AIService._format_sent_samples(samples)
        assert "unknown" in result
        assert "(no subject)" in result


class TestStyleAwareDraftsMocked:
    """Test generate_style_aware_drafts with a mocked AI provider."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = json.dumps({
            "detected_style": {
                "formality": "casual",
                "avg_length": "short",
                "greeting_style": "Hey",
                "sign_off_style": "Cheers",
                "traits": ["uses contractions"],
            },
            "drafts": [
                {"tone": "friendly", "subject": "Re: Hello", "body": "Hey! Works for me."},
                {"tone": "brief", "subject": "Re: Hello", "body": "Sure thing."},
            ],
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_style_aware_drafts(
                from_addr="alice@co.com",
                subject="Hello",
                date="2024-02-01",
                body="Want to grab coffee?",
                sent_samples=[],
                num_drafts=2,
            )

        assert result is not None
        assert isinstance(result, StyleAwareDraftResponse)
        assert result.detected_style.formality == "casual"
        assert len(result.drafts) == 2

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = "broken json {"

            result = await service.generate_style_aware_drafts(
                from_addr="alice@co.com",
                subject="Hello",
                date="2024-02-01",
                body="Hi",
                sent_samples=[],
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_sent_samples_still_works(self):
        """Style detection should still work even without sent samples."""
        mock_response = json.dumps({
            "detected_style": {
                "formality": "neutral",
                "avg_length": "medium",
                "greeting_style": "Hi",
                "sign_off_style": "Thanks",
                "traits": [],
            },
            "drafts": [
                {"tone": "formal", "subject": "Re: Test", "body": "Thank you."},
            ],
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_style_aware_drafts(
                from_addr="test@co.com",
                subject="Test",
                date="2024-02-01",
                body="Hello",
                sent_samples=[],
            )

        assert result is not None
        assert result.detected_style.formality == "neutral"

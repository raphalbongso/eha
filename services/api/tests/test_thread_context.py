"""Tests for thread context awareness: schemas, format helper, mock provider."""

import json
from unittest.mock import AsyncMock, patch

import jsonschema
import pytest

from app.services.ai_prompts import THREAD_SUMMARIZE_SCHEMA
from app.services.ai_service import AIService, DraftProposal, ThreadSummary


class TestThreadSummarizeSchema:
    """Test thread summarize JSON schema validation."""

    def test_valid_full_thread_summary(self):
        data = {
            "thread_summary": "Discussion about Q1 planning between Alice and Bob.",
            "message_count": 4,
            "participants": ["alice@co.com", "bob@co.com"],
            "key_decisions": ["Budget approved at $50k"],
            "action_items": ["Bob to send proposal by Friday"],
            "current_status": "Awaiting proposal from Bob",
            "urgency": "medium",
        }
        jsonschema.validate(instance=data, schema=THREAD_SUMMARIZE_SCHEMA)
        ts = ThreadSummary(**data)
        assert ts.message_count == 4
        assert len(ts.participants) == 2

    def test_valid_minimal_thread_summary(self):
        data = {
            "thread_summary": "Short exchange.",
            "message_count": 1,
            "participants": ["alice@co.com"],
            "key_decisions": [],
            "action_items": [],
            "current_status": "Resolved",
            "urgency": "low",
        }
        jsonschema.validate(instance=data, schema=THREAD_SUMMARIZE_SCHEMA)

    def test_missing_required_field(self):
        data = {
            "thread_summary": "Discussion.",
            "message_count": 2,
            # missing participants
            "key_decisions": [],
            "action_items": [],
            "current_status": "Open",
            "urgency": "low",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=THREAD_SUMMARIZE_SCHEMA)

    def test_invalid_urgency(self):
        data = {
            "thread_summary": "Test.",
            "message_count": 1,
            "participants": [],
            "key_decisions": [],
            "action_items": [],
            "current_status": "Done",
            "urgency": "critical",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=THREAD_SUMMARIZE_SCHEMA)

    def test_message_count_must_be_positive(self):
        data = {
            "thread_summary": "Test.",
            "message_count": 0,
            "participants": [],
            "key_decisions": [],
            "action_items": [],
            "current_status": "Done",
            "urgency": "low",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=THREAD_SUMMARIZE_SCHEMA)

    def test_extra_fields_rejected(self):
        data = {
            "thread_summary": "Test.",
            "message_count": 1,
            "participants": [],
            "key_decisions": [],
            "action_items": [],
            "current_status": "Done",
            "urgency": "low",
            "bonus": "nope",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=THREAD_SUMMARIZE_SCHEMA)


class TestFormatThreadMessages:
    """Test the _format_thread_messages static helper."""

    def test_single_message(self):
        messages = [
            {
                "from_addr": "alice@co.com",
                "date": "2024-02-01T00:00:00+00:00",
                "subject": "Hello",
                "body": "Hi there!",
            }
        ]
        result = AIService._format_thread_messages(messages)
        assert "[Message 1]" in result
        assert "alice@co.com" in result
        assert "Hi there!" in result

    def test_multiple_messages(self):
        messages = [
            {"from_addr": "a@co.com", "date": "d1", "subject": "S1", "body": "B1"},
            {"from_addr": "b@co.com", "date": "d2", "subject": "S2", "body": "B2"},
        ]
        result = AIService._format_thread_messages(messages)
        assert "[Message 1]" in result
        assert "[Message 2]" in result
        assert "a@co.com" in result
        assert "b@co.com" in result

    def test_empty_messages(self):
        result = AIService._format_thread_messages([])
        assert result == ""

    def test_missing_fields_use_defaults(self):
        messages = [{"body": "Just a body"}]
        result = AIService._format_thread_messages(messages)
        assert "unknown" in result
        assert "(no subject)" in result
        assert "Just a body" in result


class TestThreadSummarizeMocked:
    """Test summarize_thread with a mocked AI provider."""

    @pytest.mark.asyncio
    async def test_summarize_thread_success(self):
        mock_response = json.dumps({
            "thread_summary": "A planning discussion.",
            "message_count": 3,
            "participants": ["alice@co.com", "bob@co.com"],
            "key_decisions": ["Go with option A"],
            "action_items": ["Alice to draft plan"],
            "current_status": "In progress",
            "urgency": "medium",
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.summarize_thread([
                {"from_addr": "a@co.com", "date": "d", "subject": "S", "body": "B"},
            ])

        assert result is not None
        assert result.message_count == 3
        assert result.urgency == "medium"

    @pytest.mark.asyncio
    async def test_summarize_thread_invalid_json(self):
        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = "not json"

            result = await service.summarize_thread([
                {"from_addr": "a@co.com", "date": "d", "subject": "S", "body": "B"},
            ])

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_thread_drafts_success(self):
        mock_response = json.dumps({
            "drafts": [
                {"tone": "formal", "subject": "Re: Planning", "body": "Thank you for the update."},
                {"tone": "friendly", "subject": "Re: Planning", "body": "Sounds great!"},
            ]
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_thread_drafts(
                thread_messages=[
                    {"from_addr": "a@co.com", "date": "d", "subject": "S", "body": "B"},
                ],
                num_drafts=2,
            )

        assert len(result) == 2
        assert isinstance(result[0], DraftProposal)
        assert result[0].tone == "formal"

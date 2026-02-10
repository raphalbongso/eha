"""Tests for meeting prep summary feature: schema, model, response, query logic, mock AI."""

import json
from unittest.mock import AsyncMock, patch

import jsonschema
import pytest

from app.schemas.automation import MeetingPrepResponse
from app.services.ai_prompts import MEETING_PREP_SCHEMA
from app.services.ai_service import AIService, MeetingPrepSummary


class TestMeetingPrepSchema:
    """Test that the MEETING_PREP_SCHEMA validates correctly."""

    def test_valid_full_response(self):
        data = {
            "agenda_context": "Quarterly review with the sales team to discuss pipeline.",
            "key_discussion_points": [
                "Pipeline coverage for Q2",
                "New territory assignments",
            ],
            "open_action_items": [
                "Alice to share updated forecast",
                "Bob to finalize pricing sheet",
            ],
            "relevant_attachments": ["Q1_Report.pdf", "Pipeline_Dashboard.xlsx"],
        }
        jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_valid_minimal_response(self):
        data = {
            "agenda_context": "Catch-up meeting.",
            "key_discussion_points": [],
            "open_action_items": [],
            "relevant_attachments": [],
        }
        jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_missing_agenda_context_rejected(self):
        data = {
            "key_discussion_points": ["Budget"],
            "open_action_items": [],
            "relevant_attachments": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_missing_key_discussion_points_rejected(self):
        data = {
            "agenda_context": "Meeting context.",
            "open_action_items": [],
            "relevant_attachments": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_missing_open_action_items_rejected(self):
        data = {
            "agenda_context": "Meeting context.",
            "key_discussion_points": [],
            "relevant_attachments": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_missing_relevant_attachments_rejected(self):
        data = {
            "agenda_context": "Meeting context.",
            "key_discussion_points": [],
            "open_action_items": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_extra_fields_rejected(self):
        data = {
            "agenda_context": "Context.",
            "key_discussion_points": [],
            "open_action_items": [],
            "relevant_attachments": [],
            "extra": "not allowed",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_wrong_type_agenda_context_rejected(self):
        data = {
            "agenda_context": 123,
            "key_discussion_points": [],
            "open_action_items": [],
            "relevant_attachments": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_wrong_type_discussion_points_rejected(self):
        data = {
            "agenda_context": "Context.",
            "key_discussion_points": "not an array",
            "open_action_items": [],
            "relevant_attachments": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_wrong_item_type_in_action_items_rejected(self):
        data = {
            "agenda_context": "Context.",
            "key_discussion_points": [],
            "open_action_items": [123, 456],
            "relevant_attachments": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)

    def test_wrong_item_type_in_attachments_rejected(self):
        data = {
            "agenda_context": "Context.",
            "key_discussion_points": [],
            "open_action_items": [],
            "relevant_attachments": [True],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)


class TestMeetingPrepSummaryModel:
    """Test the MeetingPrepSummary Pydantic model."""

    def test_full_fields(self):
        s = MeetingPrepSummary(
            agenda_context="Review Q1 numbers with finance team.",
            key_discussion_points=["Revenue growth", "Cost reduction targets"],
            open_action_items=["Send updated slide deck"],
            relevant_attachments=["Q1_Numbers.pdf"],
        )
        assert s.agenda_context == "Review Q1 numbers with finance team."
        assert len(s.key_discussion_points) == 2
        assert len(s.open_action_items) == 1
        assert s.relevant_attachments == ["Q1_Numbers.pdf"]

    def test_empty_lists(self):
        s = MeetingPrepSummary(
            agenda_context="Quick sync.",
            key_discussion_points=[],
            open_action_items=[],
            relevant_attachments=[],
        )
        assert s.agenda_context == "Quick sync."
        assert s.key_discussion_points == []
        assert s.open_action_items == []
        assert s.relevant_attachments == []

    def test_model_dict_round_trip(self):
        data = {
            "agenda_context": "Context.",
            "key_discussion_points": ["Point A"],
            "open_action_items": ["Task 1"],
            "relevant_attachments": ["file.pdf"],
        }
        s = MeetingPrepSummary(**data)
        dumped = s.model_dump()
        assert dumped == data

    def test_schema_and_model_agree(self):
        """Data valid under the JSON schema should also be accepted by the Pydantic model."""
        data = {
            "agenda_context": "Background info.",
            "key_discussion_points": ["Topic 1", "Topic 2"],
            "open_action_items": ["Follow up with vendor"],
            "relevant_attachments": ["contract_v2.docx"],
        }
        jsonschema.validate(instance=data, schema=MEETING_PREP_SCHEMA)
        s = MeetingPrepSummary(**data)
        assert s.agenda_context == data["agenda_context"]
        assert s.key_discussion_points == data["key_discussion_points"]


class TestMeetingPrepResponseSchema:
    """Test the MeetingPrepResponse Pydantic schema from automation schemas."""

    def test_full_response(self):
        r = MeetingPrepResponse(
            event_id="evt-abc-123",
            agenda_context="Discuss roadmap priorities.",
            key_discussion_points=["Feature X timeline", "Hiring plan"],
            open_action_items=["Alice to draft PRD"],
            relevant_attachments=["roadmap.pdf"],
        )
        assert r.event_id == "evt-abc-123"
        assert r.agenda_context == "Discuss roadmap priorities."
        assert len(r.key_discussion_points) == 2
        assert len(r.open_action_items) == 1
        assert r.relevant_attachments == ["roadmap.pdf"]

    def test_empty_lists(self):
        r = MeetingPrepResponse(
            event_id="evt-empty",
            agenda_context="No prior context.",
            key_discussion_points=[],
            open_action_items=[],
            relevant_attachments=[],
        )
        assert r.key_discussion_points == []
        assert r.open_action_items == []

    def test_uuid_string_event_id(self):
        """event_id is a plain string, UUIDs should serialize fine."""
        r = MeetingPrepResponse(
            event_id="550e8400-e29b-41d4-a716-446655440000",
            agenda_context="Context.",
            key_discussion_points=[],
            open_action_items=[],
            relevant_attachments=[],
        )
        assert r.event_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_model_dump_keys(self):
        r = MeetingPrepResponse(
            event_id="evt-1",
            agenda_context="Context.",
            key_discussion_points=["A"],
            open_action_items=["B"],
            relevant_attachments=["C"],
        )
        keys = set(r.model_dump().keys())
        assert keys == {
            "event_id",
            "agenda_context",
            "key_discussion_points",
            "open_action_items",
            "relevant_attachments",
        }


class TestRelatedEmailQueryLogic:
    """Test the logic for finding related emails by attendees and subject keywords."""

    def test_attendee_matching(self):
        """Attendee emails should match from_addr via case-insensitive contains."""
        attendees = ["alice@company.com", "bob@company.com"]
        emails = [
            {"from_addr": "Alice Smith <alice@company.com>", "subject": "Lunch plans"},
            {"from_addr": "charlie@other.com", "subject": "Unrelated"},
            {"from_addr": "bob@company.com", "subject": "Project update"},
        ]
        matched = []
        for email in emails:
            for attendee in attendees:
                if attendee.lower() in email["from_addr"].lower():
                    matched.append(email)
                    break
        assert len(matched) == 2
        assert matched[0]["from_addr"] == "Alice Smith <alice@company.com>"
        assert matched[1]["from_addr"] == "bob@company.com"

    def test_subject_keyword_extraction(self):
        """Title words longer than 3 characters should be used as keywords, max 3."""
        title = "Q1 Planning Session with Finance Team"
        keywords = [w for w in title.split() if len(w) > 3][:3]
        assert keywords == ["Planning", "Session", "with"]

    def test_short_title_words_excluded(self):
        """Words with 3 or fewer characters should be excluded from keyword search."""
        title = "Q1 AI Ops"
        keywords = [w for w in title.split() if len(w) > 3]
        assert keywords == []

    def test_subject_keyword_matching(self):
        """Subject keywords should match via case-insensitive contains."""
        title = "Budget Review Meeting"
        keywords = [w for w in title.split() if len(w) > 3][:3]
        emails = [
            {"subject": "FY24 Budget Proposal", "from_addr": "cfo@co.com"},
            {"subject": "Review of Q3 results", "from_addr": "analyst@co.com"},
            {"subject": "Happy Friday!", "from_addr": "hr@co.com"},
            {"subject": "Team meeting notes", "from_addr": "pm@co.com"},
        ]
        matched_subjects = set()
        for email in emails:
            for kw in keywords:
                if kw.lower() in email["subject"].lower():
                    matched_subjects.add(email["subject"])
                    break
        assert "FY24 Budget Proposal" in matched_subjects
        assert "Review of Q3 results" in matched_subjects
        assert "Team meeting notes" in matched_subjects
        assert "Happy Friday!" not in matched_subjects

    def test_deduplication(self):
        """Emails matched by both attendee and subject should appear only once."""
        attendees = ["alice@co.com"]
        title = "Project Update"
        keywords = [w for w in title.split() if len(w) > 3][:3]

        emails = [
            {"from_addr": "alice@co.com", "subject": "Project Update Notes", "id": "1"},
            {"from_addr": "bob@co.com", "subject": "Unrelated", "id": "2"},
        ]

        seen_ids = set()
        related = []

        # Attendee pass
        for email in emails:
            for attendee in attendees:
                if attendee.lower() in email["from_addr"].lower():
                    if email["id"] not in seen_ids:
                        seen_ids.add(email["id"])
                        related.append(email)
                    break

        # Subject keyword pass
        for email in emails:
            for kw in keywords:
                if kw.lower() in email["subject"].lower():
                    if email["id"] not in seen_ids:
                        seen_ids.add(email["id"])
                        related.append(email)
                    break

        # Email "1" matched both attendee and keyword but should appear once
        assert len(related) == 1
        assert related[0]["id"] == "1"

    def test_no_attendees_uses_subject_only(self):
        """When there are no attendees, only subject keywords are used."""
        attendees = []
        title = "Design Sprint Kickoff"
        keywords = [w for w in title.split() if len(w) > 3][:3]

        emails = [
            {"from_addr": "lead@co.com", "subject": "Sprint planning", "id": "1"},
            {"from_addr": "mgr@co.com", "subject": "Design review", "id": "2"},
        ]

        seen_ids = set()
        related = []

        for email in emails:
            for kw in keywords:
                if kw.lower() in email["subject"].lower():
                    if email["id"] not in seen_ids:
                        seen_ids.add(email["id"])
                        related.append(email)
                    break

        assert len(related) == 2


class TestMeetingPrepMocked:
    """Test generate_meeting_prep with a mocked AI provider."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = json.dumps({
            "agenda_context": "Follow-up on last week's sprint review with the eng team.",
            "key_discussion_points": [
                "Unresolved blockers from sprint 14",
                "Capacity planning for sprint 15",
            ],
            "open_action_items": [
                "Bob to share updated velocity chart",
                "Alice to confirm scope with product",
            ],
            "relevant_attachments": ["sprint14_retro.pdf"],
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_meeting_prep(
                meeting_title="Sprint 15 Planning",
                meeting_time="2024-02-05T10:00:00Z",
                attendees=["alice@co.com", "bob@co.com"],
                related_emails=[
                    {
                        "from_addr": "alice@co.com",
                        "date": "2024-02-01",
                        "subject": "Sprint 14 retro",
                        "body": "Attached are the notes from last sprint.",
                    },
                ],
            )

        assert result is not None
        assert isinstance(result, MeetingPrepSummary)
        assert "sprint review" in result.agenda_context.lower()
        assert len(result.key_discussion_points) == 2
        assert len(result.open_action_items) == 2
        assert result.relevant_attachments == ["sprint14_retro.pdf"]

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = "not valid json {"

            result = await service.generate_meeting_prep(
                meeting_title="Standup",
                meeting_time="2024-02-05T09:00:00Z",
                attendees=["dev@co.com"],
                related_emails=[],
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_schema_violation_returns_none(self):
        """Response missing required fields should cause validation failure."""
        mock_response = json.dumps({
            "agenda_context": "Some context.",
            # missing key_discussion_points, open_action_items, relevant_attachments
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_meeting_prep(
                meeting_title="Sync",
                meeting_time="2024-02-05T14:00:00Z",
                attendees=[],
                related_emails=[],
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extra_fields_returns_none(self):
        """Response with extra fields should fail schema validation."""
        mock_response = json.dumps({
            "agenda_context": "Context.",
            "key_discussion_points": [],
            "open_action_items": [],
            "relevant_attachments": [],
            "surprise": "not allowed",
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_meeting_prep(
                meeting_title="Sync",
                meeting_time="2024-02-05T14:00:00Z",
                attendees=[],
                related_emails=[],
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_related_emails(self):
        """Meeting prep should work even with no related emails."""
        mock_response = json.dumps({
            "agenda_context": "No prior email context available.",
            "key_discussion_points": [],
            "open_action_items": [],
            "relevant_attachments": [],
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_meeting_prep(
                meeting_title="Ad-hoc Sync",
                meeting_time="2024-02-05T16:00:00Z",
                attendees=["teammate@co.com"],
                related_emails=[],
            )

        assert result is not None
        assert result.agenda_context == "No prior email context available."
        assert result.key_discussion_points == []

    @pytest.mark.asyncio
    async def test_markdown_code_block_response(self):
        """AI responses wrapped in markdown code blocks should still parse."""
        inner = json.dumps({
            "agenda_context": "Wrapped response.",
            "key_discussion_points": ["Topic"],
            "open_action_items": [],
            "relevant_attachments": [],
        })
        mock_response = f"```json\n{inner}\n```"

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            result = await service.generate_meeting_prep(
                meeting_title="Design Review",
                meeting_time="2024-02-06T11:00:00Z",
                attendees=[],
                related_emails=[],
            )

        assert result is not None
        assert result.agenda_context == "Wrapped response."
        assert result.key_discussion_points == ["Topic"]

    @pytest.mark.asyncio
    async def test_prompt_includes_attendees_and_title(self):
        """Verify that the prompt sent to the provider contains attendees and title."""
        mock_response = json.dumps({
            "agenda_context": "Context.",
            "key_discussion_points": [],
            "open_action_items": [],
            "relevant_attachments": [],
        })

        with patch.object(AIService, "__init__", lambda self, settings: None):
            service = AIService.__new__(AIService)
            service._provider = AsyncMock()
            service._provider.complete.return_value = mock_response

            await service.generate_meeting_prep(
                meeting_title="Quarterly Business Review",
                meeting_time="2024-03-01T15:00:00Z",
                attendees=["cfo@co.com", "ceo@co.com"],
                related_emails=[],
            )

        prompt_sent = service._provider.complete.call_args[0][0]
        assert "Quarterly Business Review" in prompt_sent
        assert "cfo@co.com" in prompt_sent
        assert "ceo@co.com" in prompt_sent

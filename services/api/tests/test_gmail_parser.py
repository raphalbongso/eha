"""Unit tests for Gmail message parser."""

from datetime import datetime, timezone

import pytest

from app.services.gmail_parser import ParsedMessage, parse_gmail_message


class TestParseGmailMessage:
    def test_basic_message(self, sample_gmail_message):
        result = parse_gmail_message(sample_gmail_message)

        assert isinstance(result, ParsedMessage)
        assert result.message_id == "msg_001"
        assert result.thread_id == "thread_001"
        assert result.subject == "Team Meeting Tomorrow"
        assert result.from_addr == "alice@company.com"
        assert result.from_name == "Alice Smith"
        assert "bob@company.com" in result.to_addrs
        assert "charlie@company.com" in result.to_addrs
        assert result.snippet == "Please join our team meeting tomorrow at 3pm in Room 42."
        assert result.has_attachment is False
        assert "INBOX" in result.label_ids
        assert "IMPORTANT" in result.label_ids

    def test_body_extraction(self, sample_gmail_message):
        result = parse_gmail_message(sample_gmail_message)

        assert result.body_text is not None
        assert "team meeting" in result.body_text.lower()
        assert "Room 42" in result.body_text

    def test_received_at_parsing(self, sample_gmail_message):
        result = parse_gmail_message(sample_gmail_message)

        assert result.received_at is not None
        assert isinstance(result.received_at, datetime)
        assert result.received_at.tzinfo == timezone.utc

    def test_attachment_detection(self, sample_gmail_message_with_attachment):
        result = parse_gmail_message(sample_gmail_message_with_attachment)

        assert result.has_attachment is True
        assert result.subject == "Q4 Report"

    def test_empty_message(self):
        raw = {"id": "msg_empty", "payload": {"headers": [], "mimeType": "text/plain", "body": {}}}
        result = parse_gmail_message(raw)

        assert result.message_id == "msg_empty"
        assert result.subject is None
        assert result.from_addr is None
        assert result.body_text is None

    def test_missing_fields_graceful(self):
        raw = {"id": "msg_minimal"}
        result = parse_gmail_message(raw)

        assert result.message_id == "msg_minimal"
        assert result.thread_id is None
        assert result.label_ids == []


class TestMultipleRecipients:
    def test_multiple_to(self):
        raw = {
            "id": "msg_multi",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "To", "value": "a@test.com, b@test.com, c@test.com"},
                ],
                "body": {},
            },
        }
        result = parse_gmail_message(raw)
        assert len(result.to_addrs) == 3
        assert "a@test.com" in result.to_addrs
        assert "c@test.com" in result.to_addrs


class TestHTMLSanitization:
    def test_html_only_message(self):
        import base64

        html = "<html><body><p>Hello <b>World</b></p><br/><p>Second paragraph</p></body></html>"
        encoded = base64.urlsafe_b64encode(html.encode()).decode()

        raw = {
            "id": "msg_html",
            "payload": {
                "mimeType": "text/html",
                "headers": [],
                "body": {"data": encoded},
            },
        }
        result = parse_gmail_message(raw)

        assert result.body_text is not None
        assert "Hello" in result.body_text
        assert "World" in result.body_text
        # HTML tags should be stripped
        assert "<b>" not in result.body_text
        assert "<p>" not in result.body_text

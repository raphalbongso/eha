"""Shared test fixtures."""

import uuid
from datetime import datetime, timezone

import pytest


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.UUID("12345678-1234-1234-1234-123456789abc")


@pytest.fixture
def sample_gmail_message() -> dict:
    """A realistic Gmail API message response."""
    return {
        "id": "msg_001",
        "threadId": "thread_001",
        "labelIds": ["INBOX", "IMPORTANT"],
        "snippet": "Please join our team meeting tomorrow at 3pm in Room 42.",
        "internalDate": "1706745600000",  # 2024-02-01 00:00:00 UTC
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Alice Smith <alice@company.com>"},
                {"name": "To", "value": "bob@company.com, charlie@company.com"},
                {"name": "Subject", "value": "Team Meeting Tomorrow"},
                {"name": "Date", "value": "Thu, 01 Feb 2024 00:00:00 +0000"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        # base64url of "Please join our team meeting tomorrow at 3pm in Room 42.\n\nLet me know if you can make it.\n\nBest,\nAlice"
                        "data": "UGxlYXNlIGpvaW4gb3VyIHRlYW0gbWVldGluZyB0b21vcnJvdyBhdCAzcG0gaW4gUm9vbSA0Mi4KCkxldCBtZSBrbm93IGlmIHlvdSBjYW4gbWFrZSBpdC4KCkJlc3QsCkFsaWNl"
                    },
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": "PHA-UGxlYXNlIGpvaW4gb3VyIHRlYW0gbWVldGluZyB0b21vcnJvdyBhdCAzcG0gaW4gUm9vbSA0Mi48L3A-"
                    },
                },
            ],
        },
    }


@pytest.fixture
def sample_gmail_message_with_attachment() -> dict:
    """Gmail message with an attachment."""
    return {
        "id": "msg_002",
        "threadId": "thread_002",
        "labelIds": ["INBOX"],
        "snippet": "Please find the report attached.",
        "internalDate": "1706832000000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "reports@company.com"},
                {"name": "To", "value": "bob@company.com"},
                {"name": "Subject", "value": "Q4 Report"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": "UGxlYXNlIGZpbmQgdGhlIHJlcG9ydCBhdHRhY2hlZC4="
                    },
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "Q4_Report.pdf",
                    "body": {"attachmentId": "att_001", "size": 102400},
                },
            ],
        },
    }

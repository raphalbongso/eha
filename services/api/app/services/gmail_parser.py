"""Gmail message parsing and sanitization."""

import base64
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr

logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """Parsed and sanitized email message."""

    message_id: str
    thread_id: str | None
    subject: str | None
    from_addr: str | None
    from_name: str | None
    to_addrs: list[str]
    snippet: str | None
    body_text: str | None
    body_html: str | None
    received_at: datetime | None
    has_attachment: bool
    label_ids: list[str]
    internal_date: int | None


def _decode_base64url(data: str) -> str:
    """Decode base64url encoded string."""
    padded = data + "=" * (4 - len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception:
        logger.warning("Failed to decode base64url data")
        return ""


def _get_header(headers: list[dict], name: str) -> str | None:
    """Get a header value by name (case-insensitive)."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _extract_body(payload: dict) -> tuple[str | None, str | None]:
    """Recursively extract text and HTML body from message payload."""
    text_body = None
    html_body = None

    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            text_body = _decode_base64url(data)
    elif mime_type == "text/html":
        data = payload.get("body", {}).get("data")
        if data:
            html_body = _decode_base64url(data)
    elif mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            t, h = _extract_body(part)
            if t and not text_body:
                text_body = t
            if h and not html_body:
                html_body = h

    return text_body, html_body


def _has_attachments(payload: dict) -> bool:
    """Check if message has attachments."""
    if payload.get("filename"):
        return True
    for part in payload.get("parts", []):
        if _has_attachments(part):
            return True
    return False


def _sanitize_html(html: str) -> str:
    """Strip HTML tags for plain text extraction (basic sanitization)."""
    clean = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", "", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def parse_gmail_message(raw_message: dict) -> ParsedMessage:
    """Parse a raw Gmail API message into a structured format.

    Args:
        raw_message: Raw message dict from Gmail API messages.get()

    Returns:
        ParsedMessage with extracted and sanitized fields.
    """
    message_id = raw_message.get("id", "")
    thread_id = raw_message.get("threadId")
    snippet = raw_message.get("snippet")
    label_ids = raw_message.get("labelIds", [])
    internal_date = raw_message.get("internalDate")

    payload = raw_message.get("payload", {})
    headers = payload.get("headers", [])

    subject = _get_header(headers, "Subject")
    from_raw = _get_header(headers, "From") or ""
    to_raw = _get_header(headers, "To") or ""

    from_name, from_addr = parseaddr(from_raw)

    # Parse multiple To addresses
    to_addrs = []
    for addr_part in to_raw.split(","):
        _, addr = parseaddr(addr_part.strip())
        if addr:
            to_addrs.append(addr)

    # Parse received date
    received_at = None
    if internal_date:
        try:
            ts = int(internal_date) / 1000  # Gmail uses milliseconds
            received_at = datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            pass

    # Extract body
    text_body, html_body = _extract_body(payload)
    if not text_body and html_body:
        text_body = _sanitize_html(html_body)

    has_attachment = _has_attachments(payload)

    return ParsedMessage(
        message_id=message_id,
        thread_id=thread_id,
        subject=subject,
        from_addr=from_addr or None,
        from_name=from_name or None,
        to_addrs=to_addrs,
        snippet=snippet,
        body_text=text_body,
        body_html=html_body,
        received_at=received_at,
        has_attachment=has_attachment,
        label_ids=label_ids,
        internal_date=int(internal_date) if internal_date else None,
    )

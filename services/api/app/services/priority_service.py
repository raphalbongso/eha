"""Heuristic priority scoring for inbox messages.

Uses metadata from ProcessedMessage fields — no AI calls, no Gmail fetches.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


# Keywords that indicate high-priority emails
URGENT_KEYWORDS = re.compile(
    r"\b(urgent|asap|immediately|deadline|critical|action required|time.?sensitive|eod|end of day)\b",
    re.IGNORECASE,
)

# Keywords that indicate lower-priority (informational) emails
LOW_PRIORITY_KEYWORDS = re.compile(
    r"\b(unsubscribe|newsletter|no.?reply|noreply|digest|weekly update|monthly report|fyi)\b",
    re.IGNORECASE,
)


def compute_heuristic_priority(message: Any) -> dict[str, Any]:
    """Compute a heuristic priority score from ProcessedMessage fields.

    Args:
        message: A ProcessedMessage model instance (or any object with the same attributes).

    Returns:
        dict with "score" (int 0-100) and "signals" (list[str]).
    """
    score = 50  # baseline
    signals: list[str] = []

    subject = message.subject or ""
    snippet = message.snippet or ""
    from_addr = message.from_addr or ""
    label_ids_raw = message.label_ids or ""
    labels = {lbl.strip().upper() for lbl in label_ids_raw.split(",") if lbl.strip()}
    has_attachment = getattr(message, "has_attachment", False)
    received_at = getattr(message, "received_at", None)

    text = f"{subject} {snippet}"

    # --- Label signals ---
    if "IMPORTANT" in labels:
        score += 15
        signals.append("marked important by Gmail")

    if "STARRED" in labels:
        score += 10
        signals.append("starred")

    if "CATEGORY_PROMOTIONS" in labels or "CATEGORY_SOCIAL" in labels:
        score -= 15
        signals.append("promotional or social")

    if "CATEGORY_UPDATES" in labels:
        score -= 5
        signals.append("updates category")

    if "SPAM" in labels:
        score -= 30
        signals.append("spam")

    # --- Subject / snippet keyword signals ---
    if URGENT_KEYWORDS.search(text):
        score += 20
        signals.append("contains urgent keywords")

    if LOW_PRIORITY_KEYWORDS.search(text):
        score -= 15
        signals.append("contains low-priority keywords")

    # --- Sender signals ---
    if "noreply" in from_addr.lower() or "no-reply" in from_addr.lower():
        score -= 10
        signals.append("sent from no-reply address")

    # --- Attachment signal ---
    if has_attachment:
        score += 5
        signals.append("has attachment")

    # --- Recency signal ---
    if received_at is not None:
        now = datetime.now(timezone.utc)
        age_hours = (now - received_at).total_seconds() / 3600
        if age_hours < 1:
            score += 10
            signals.append("received within last hour")
        elif age_hours < 6:
            score += 5
            signals.append("received within last 6 hours")
        elif age_hours > 72:
            score -= 5
            signals.append("older than 3 days")

    # Clamp to 0-100
    score = max(0, min(100, score))

    return {"score": score, "signals": signals}

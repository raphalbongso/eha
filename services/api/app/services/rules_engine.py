"""Rules engine for matching emails against user-defined rules."""

import logging
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo

from app.services.gmail_parser import ParsedMessage

logger = logging.getLogger(__name__)


def _match_condition(condition: dict[str, Any], message: ParsedMessage) -> bool:
    """Evaluate a single condition against a parsed message."""
    ctype = condition.get("type", "")
    value = condition.get("value")

    if ctype == "from_contains":
        if not message.from_addr:
            return False
        return str(value).lower() in message.from_addr.lower()

    elif ctype == "subject_contains":
        if not message.subject:
            return False
        return str(value).lower() in message.subject.lower()

    elif ctype == "has_attachment":
        return message.has_attachment == bool(value)

    elif ctype == "label":
        return str(value) in message.label_ids

    elif ctype == "body_keywords":
        if not isinstance(value, list) or not message.body_text:
            return False
        body_lower = message.body_text.lower()
        return any(kw.lower() in body_lower for kw in value)

    elif ctype == "time_window":
        if not isinstance(value, dict) or not message.received_at:
            return False
        try:
            tz_name = value.get("timezone", "UTC")
            tz = ZoneInfo(tz_name)
            msg_time = message.received_at.astimezone(tz).time()
            start = time.fromisoformat(value["start"])
            end = time.fromisoformat(value["end"])
            if start <= end:
                return start <= msg_time <= end
            else:
                # Overnight window (e.g. 22:00 - 06:00)
                return msg_time >= start or msg_time <= end
        except (KeyError, ValueError) as e:
            logger.warning("Invalid time_window condition: %s", e)
            return False

    else:
        logger.warning("Unknown condition type: %s", ctype)
        return False


def evaluate_rule(rule_conditions: dict[str, Any], message: ParsedMessage) -> bool:
    """Evaluate a rule's conditions against a parsed message.

    Args:
        rule_conditions: Dict with "logic" (AND/OR) and "conditions" list.
        message: The parsed email message.

    Returns:
        True if the rule matches the message.
    """
    logic = rule_conditions.get("logic", "AND").upper()
    conditions = rule_conditions.get("conditions", [])

    if not conditions:
        return False

    results = [_match_condition(c, message) for c in conditions]

    if logic == "OR":
        return any(results)
    else:  # AND (default)
        return all(results)


def match_rules(
    rules: list[dict[str, Any]],
    message: ParsedMessage,
) -> list[dict[str, Any]]:
    """Match a message against a list of rules.

    Args:
        rules: List of dicts with "id", "conditions", and optionally "name".
        message: The parsed email message.

    Returns:
        List of matching rules.
    """
    matched = []
    for rule in rules:
        conditions = rule.get("conditions", {})
        if evaluate_rule(conditions, message):
            matched.append(rule)
    return matched

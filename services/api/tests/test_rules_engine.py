"""Unit tests for the rules engine."""

from datetime import datetime, timezone

from app.services.gmail_parser import ParsedMessage
from app.services.rules_engine import evaluate_rule, match_rules


def _make_message(**overrides) -> ParsedMessage:
    """Helper to create a ParsedMessage with defaults."""
    defaults = {
        "message_id": "msg_test",
        "thread_id": "thread_test",
        "subject": "Test Subject",
        "from_addr": "alice@company.com",
        "from_name": "Alice",
        "to_addrs": ["bob@company.com"],
        "snippet": "Test snippet",
        "body_text": "This is the email body with important content.",
        "body_html": None,
        "received_at": datetime(2024, 2, 1, 14, 30, tzinfo=timezone.utc),
        "has_attachment": False,
        "label_ids": ["INBOX", "IMPORTANT"],
        "internal_date": 1706795400000,
    }
    defaults.update(overrides)
    return ParsedMessage(**defaults)


class TestFromContains:
    def test_match(self):
        msg = _make_message(from_addr="alice@company.com")
        conditions = {"logic": "AND", "conditions": [{"type": "from_contains", "value": "alice"}]}
        assert evaluate_rule(conditions, msg) is True

    def test_no_match(self):
        msg = _make_message(from_addr="bob@company.com")
        conditions = {"logic": "AND", "conditions": [{"type": "from_contains", "value": "alice"}]}
        assert evaluate_rule(conditions, msg) is False

    def test_case_insensitive(self):
        msg = _make_message(from_addr="Alice@Company.com")
        conditions = {"logic": "AND", "conditions": [{"type": "from_contains", "value": "alice"}]}
        assert evaluate_rule(conditions, msg) is True

    def test_null_from(self):
        msg = _make_message(from_addr=None)
        conditions = {"logic": "AND", "conditions": [{"type": "from_contains", "value": "alice"}]}
        assert evaluate_rule(conditions, msg) is False


class TestSubjectContains:
    def test_match(self):
        msg = _make_message(subject="Urgent: Team Meeting")
        conditions = {"logic": "AND", "conditions": [{"type": "subject_contains", "value": "urgent"}]}
        assert evaluate_rule(conditions, msg) is True

    def test_no_match(self):
        msg = _make_message(subject="Weekly Update")
        conditions = {"logic": "AND", "conditions": [{"type": "subject_contains", "value": "urgent"}]}
        assert evaluate_rule(conditions, msg) is False


class TestHasAttachment:
    def test_has_attachment_true(self):
        msg = _make_message(has_attachment=True)
        conditions = {"logic": "AND", "conditions": [{"type": "has_attachment", "value": True}]}
        assert evaluate_rule(conditions, msg) is True

    def test_has_attachment_false(self):
        msg = _make_message(has_attachment=False)
        conditions = {"logic": "AND", "conditions": [{"type": "has_attachment", "value": True}]}
        assert evaluate_rule(conditions, msg) is False


class TestLabel:
    def test_label_match(self):
        msg = _make_message(label_ids=["INBOX", "IMPORTANT"])
        conditions = {"logic": "AND", "conditions": [{"type": "label", "value": "IMPORTANT"}]}
        assert evaluate_rule(conditions, msg) is True

    def test_label_no_match(self):
        msg = _make_message(label_ids=["INBOX"])
        conditions = {"logic": "AND", "conditions": [{"type": "label", "value": "IMPORTANT"}]}
        assert evaluate_rule(conditions, msg) is False


class TestBodyKeywords:
    def test_keyword_match(self):
        msg = _make_message(body_text="The deadline is approaching fast, need ASAP response.")
        conditions = {
            "logic": "AND",
            "conditions": [{"type": "body_keywords", "value": ["deadline", "urgent"]}],
        }
        assert evaluate_rule(conditions, msg) is True

    def test_no_keyword_match(self):
        msg = _make_message(body_text="Just wanted to say hello.")
        conditions = {
            "logic": "AND",
            "conditions": [{"type": "body_keywords", "value": ["deadline", "urgent"]}],
        }
        assert evaluate_rule(conditions, msg) is False

    def test_keyword_with_null_body(self):
        msg = _make_message(body_text=None)
        conditions = {
            "logic": "AND",
            "conditions": [{"type": "body_keywords", "value": ["deadline"]}],
        }
        assert evaluate_rule(conditions, msg) is False


class TestTimeWindow:
    def test_within_window(self):
        # 14:30 UTC is within 09:00-17:00 UTC
        msg = _make_message(received_at=datetime(2024, 2, 1, 14, 30, tzinfo=timezone.utc))
        conditions = {
            "logic": "AND",
            "conditions": [
                {"type": "time_window", "value": {"start": "09:00", "end": "17:00", "timezone": "UTC"}}
            ],
        }
        assert evaluate_rule(conditions, msg) is True

    def test_outside_window(self):
        # 03:00 UTC is outside 09:00-17:00 UTC
        msg = _make_message(received_at=datetime(2024, 2, 1, 3, 0, tzinfo=timezone.utc))
        conditions = {
            "logic": "AND",
            "conditions": [
                {"type": "time_window", "value": {"start": "09:00", "end": "17:00", "timezone": "UTC"}}
            ],
        }
        assert evaluate_rule(conditions, msg) is False

    def test_overnight_window(self):
        # 23:00 UTC should match 22:00-06:00 overnight window
        msg = _make_message(received_at=datetime(2024, 2, 1, 23, 0, tzinfo=timezone.utc))
        conditions = {
            "logic": "AND",
            "conditions": [
                {"type": "time_window", "value": {"start": "22:00", "end": "06:00", "timezone": "UTC"}}
            ],
        }
        assert evaluate_rule(conditions, msg) is True


class TestLogicCombinations:
    def test_and_all_match(self):
        msg = _make_message(from_addr="alice@company.com", subject="Urgent Report")
        conditions = {
            "logic": "AND",
            "conditions": [
                {"type": "from_contains", "value": "alice"},
                {"type": "subject_contains", "value": "urgent"},
            ],
        }
        assert evaluate_rule(conditions, msg) is True

    def test_and_partial_match(self):
        msg = _make_message(from_addr="alice@company.com", subject="Weekly Update")
        conditions = {
            "logic": "AND",
            "conditions": [
                {"type": "from_contains", "value": "alice"},
                {"type": "subject_contains", "value": "urgent"},
            ],
        }
        assert evaluate_rule(conditions, msg) is False

    def test_or_one_match(self):
        msg = _make_message(from_addr="bob@company.com", subject="Urgent!")
        conditions = {
            "logic": "OR",
            "conditions": [
                {"type": "from_contains", "value": "alice"},
                {"type": "subject_contains", "value": "urgent"},
            ],
        }
        assert evaluate_rule(conditions, msg) is True

    def test_or_no_match(self):
        msg = _make_message(from_addr="bob@company.com", subject="Hello")
        conditions = {
            "logic": "OR",
            "conditions": [
                {"type": "from_contains", "value": "alice"},
                {"type": "subject_contains", "value": "urgent"},
            ],
        }
        assert evaluate_rule(conditions, msg) is False

    def test_empty_conditions(self):
        msg = _make_message()
        conditions = {"logic": "AND", "conditions": []}
        assert evaluate_rule(conditions, msg) is False


class TestMatchRules:
    def test_multiple_rules_match(self):
        msg = _make_message(from_addr="boss@company.com", has_attachment=True)
        rules = [
            {
                "id": "rule1",
                "name": "Boss emails",
                "conditions": {"logic": "AND", "conditions": [{"type": "from_contains", "value": "boss"}]},
            },
            {
                "id": "rule2",
                "name": "With attachments",
                "conditions": {"logic": "AND", "conditions": [{"type": "has_attachment", "value": True}]},
            },
            {
                "id": "rule3",
                "name": "Urgent from Alice",
                "conditions": {"logic": "AND", "conditions": [{"type": "from_contains", "value": "alice"}]},
            },
        ]
        matched = match_rules(rules, msg)
        assert len(matched) == 2
        assert matched[0]["id"] == "rule1"
        assert matched[1]["id"] == "rule2"

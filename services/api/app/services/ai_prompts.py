"""Prompt templates and JSON schemas for AI service."""

SUMMARIZE_PROMPT = """Summarize the following email concisely in 2-3 sentences.
Focus on: who sent it, the main topic, any action items, and urgency level.

Email:
---
From: {from_addr}
Subject: {subject}
Date: {date}

{body}
---

Respond ONLY in JSON:
{{
  "summary": "string",
  "action_items": ["string"] or [],
  "urgency": "low" | "medium" | "high"
}}"""

DRAFT_REPLY_PROMPT = """Generate {num_drafts} reply options for this email.
Each reply should have a different tone and length.

Original email:
---
From: {from_addr}
Subject: {subject}
Date: {date}

{body}
---

User context (if any): {user_context}

Respond ONLY in JSON:
{{
  "drafts": [
    {{
      "tone": "formal" | "friendly" | "brief",
      "subject": "Re: ...",
      "body": "string"
    }}
  ]
}}

Rules:
- Generate exactly {num_drafts} drafts
- Each draft should be a complete, ready-to-send reply
- Do NOT invent facts or commitments the user hasn't specified
- Keep replies professional and contextually appropriate"""

EXTRACT_EVENT_PROMPT = """Extract calendar event from this email. Respond ONLY in JSON:
{{
  "title": "string or null",
  "start_datetime": "ISO8601 or null",
  "end_datetime": "ISO8601 or null",
  "duration_minutes": number or null,
  "location": "string or null",
  "attendees": ["email"] or null,
  "confidence": 0.0 to 1.0
}}

Rules:
- If date/time is ambiguous or missing, set confidence below 0.5
- Do NOT invent information not present in the email
- Use ISO8601 format for all datetime values
- If only a date is mentioned without time, set confidence below 0.7
- Extract attendees only if email addresses are explicitly mentioned

Email:
---
From: {from_addr}
Subject: {subject}
Date: {date}

{body}
---"""

# JSON schemas for output validation
SUMMARY_SCHEMA = {
    "type": "object",
    "required": ["summary", "action_items", "urgency"],
    "properties": {
        "summary": {"type": "string"},
        "action_items": {"type": "array", "items": {"type": "string"}},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "additionalProperties": False,
}

DRAFT_SCHEMA = {
    "type": "object",
    "required": ["drafts"],
    "properties": {
        "drafts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["tone", "subject", "body"],
                "properties": {
                    "tone": {"type": "string", "enum": ["formal", "friendly", "brief"]},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
    },
    "additionalProperties": False,
}

EVENT_SCHEMA = {
    "type": "object",
    "required": ["title", "confidence"],
    "properties": {
        "title": {"type": ["string", "null"]},
        "start_datetime": {"type": ["string", "null"]},
        "end_datetime": {"type": ["string", "null"]},
        "duration_minutes": {"type": ["number", "null"]},
        "location": {"type": ["string", "null"]},
        "attendees": {
            "oneOf": [
                {"type": "array", "items": {"type": "string"}},
                {"type": "null"},
            ]
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "additionalProperties": False,
}

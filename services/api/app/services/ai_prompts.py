"""Prompt templates and JSON schemas for AI service."""

SUMMARIZE_PROMPT = """Summarize the following email concisely in 2-3 sentences.
Focus on: who sent it, the main topic, any action items, and urgency level.
Also categorize the email and assign a priority score.

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
  "urgency": "low" | "medium" | "high",
  "category": "general" | "invoice" | "meeting" | "newsletter" | "action_required" | "shipping" | "security",
  "priority_score": 0-100,
  "priority_signals": ["string"]
}}

Rules:
- category: classify the email into exactly one of the given categories
- priority_score: integer 0-100 indicating importance (100 = most important)
- priority_signals: list of reasons for the priority score (e.g. "contains deadline", "from known sender", "requires response")"""

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
    "required": ["summary", "action_items", "urgency", "category", "priority_score", "priority_signals"],
    "properties": {
        "summary": {"type": "string"},
        "action_items": {"type": "array", "items": {"type": "string"}},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "category": {
            "type": "string",
            "enum": [
                "general",
                "invoice",
                "meeting",
                "newsletter",
                "action_required",
                "shipping",
                "security",
            ],
        },
        "priority_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "priority_signals": {"type": "array", "items": {"type": "string"}},
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

# --- Thread context prompts & schemas ---

THREAD_SUMMARIZE_PROMPT = """Summarize the following email thread. Provide an overview of the
conversation, identify key decisions, action items, and the current status.

Thread messages (oldest first):
---
{thread_messages}
---

Respond ONLY in JSON:
{{
  "thread_summary": "string",
  "message_count": number,
  "participants": ["string"],
  "key_decisions": ["string"],
  "action_items": ["string"],
  "current_status": "string",
  "urgency": "low" | "medium" | "high"
}}"""

THREAD_SUMMARIZE_SCHEMA = {
    "type": "object",
    "required": [
        "thread_summary",
        "message_count",
        "participants",
        "key_decisions",
        "action_items",
        "current_status",
        "urgency",
    ],
    "properties": {
        "thread_summary": {"type": "string"},
        "message_count": {"type": "integer", "minimum": 1},
        "participants": {"type": "array", "items": {"type": "string"}},
        "key_decisions": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": {"type": "string"}},
        "current_status": {"type": "string"},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "additionalProperties": False,
}

THREAD_SMART_REPLY_PROMPT = """Generate {num_drafts} reply options for this email thread.
Consider the full thread context when crafting replies.

Thread messages (oldest first):
---
{thread_messages}
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
- Consider the full thread context, not just the last message
- Each draft should be a complete, ready-to-send reply
- Do NOT invent facts or commitments the user hasn't specified
- Keep replies professional and contextually appropriate"""

THREAD_SMART_REPLY_SCHEMA = DRAFT_SCHEMA  # Same structure as single-message drafts

# --- Style-aware drafts prompts & schemas ---

STYLE_AWARE_DRAFT_PROMPT = """Analyze the user's writing style from their sent emails below,
then generate {num_drafts} reply options that match their style.

User's sent email samples:
---
{sent_samples}
---

Email to reply to:
---
From: {from_addr}
Subject: {subject}
Date: {date}

{body}
---

User context (if any): {user_context}

Respond ONLY in JSON:
{{
  "detected_style": {{
    "formality": "casual" | "neutral" | "formal",
    "avg_length": "short" | "medium" | "long",
    "greeting_style": "string",
    "sign_off_style": "string",
    "traits": ["string"]
  }},
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
- Match the user's detected writing style (formality, length, greetings, sign-offs)
- Each draft should be a complete, ready-to-send reply
- Do NOT invent facts or commitments the user hasn't specified"""

STYLE_DRAFT_SCHEMA = {
    "type": "object",
    "required": ["detected_style", "drafts"],
    "properties": {
        "detected_style": {
            "type": "object",
            "required": ["formality", "avg_length", "greeting_style", "sign_off_style", "traits"],
            "properties": {
                "formality": {"type": "string", "enum": ["casual", "neutral", "formal"]},
                "avg_length": {"type": "string", "enum": ["short", "medium", "long"]},
                "greeting_style": {"type": "string"},
                "sign_off_style": {"type": "string"},
                "traits": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
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
        },
    },
    "additionalProperties": False,
}

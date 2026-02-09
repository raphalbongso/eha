"""Provider-agnostic AI service interface."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import jsonschema
from pydantic import BaseModel

from app.config import Settings
from app.services.ai_prompts import (
    DRAFT_REPLY_PROMPT,
    DRAFT_SCHEMA,
    EVENT_SCHEMA,
    EXTRACT_EVENT_PROMPT,
    SUMMARIZE_PROMPT,
    SUMMARY_SCHEMA,
)

logger = logging.getLogger(__name__)


class Summary(BaseModel):
    summary: str
    action_items: list[str]
    urgency: str


class DraftProposal(BaseModel):
    tone: str
    subject: str
    body: str


class EventProposal(BaseModel):
    title: str | None
    start_datetime: str | None
    end_datetime: str | None
    duration_minutes: int | None
    location: str | None
    attendees: list[str] | None
    confidence: float


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Send a prompt and return the completion text."""
        ...


class OpenAIProvider(AIProvider):
    """OpenAI-compatible API provider."""

    def __init__(self, api_key: str, model: str) -> None:
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are a helpful email assistant. Always respond in valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or "{}"


class AnthropicProvider(AIProvider):
    """Anthropic API provider."""

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, prompt: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt + "\n\nRespond ONLY with valid JSON, no other text."},
            ],
        )
        return response.content[0].text


def _validate_json(data: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Validate parsed JSON against schema."""
    try:
        jsonschema.validate(instance=data, schema=schema)
        return True
    except jsonschema.ValidationError as e:
        logger.warning("AI output validation failed: %s", e.message)
        return False


def _parse_json_safe(text: str) -> dict[str, Any] | None:
    """Parse JSON from AI response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last line (code block markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse AI response as JSON")
        return None


class AIService:
    """Provider-agnostic AI service."""

    def __init__(self, settings: Settings) -> None:
        if settings.ai_provider == "openai":
            self._provider = OpenAIProvider(
                api_key=settings.openai_api_key.get_secret_value(),
                model=settings.openai_model,
            )
        elif settings.ai_provider == "anthropic":
            self._provider = AnthropicProvider(
                api_key=settings.anthropic_api_key.get_secret_value(),
                model=settings.anthropic_model,
            )
        else:
            raise ValueError(f"Unknown AI provider: {settings.ai_provider}")

    async def summarize(
        self,
        from_addr: str,
        subject: str,
        date: str,
        body: str,
    ) -> Summary | None:
        """Summarize an email."""
        prompt = SUMMARIZE_PROMPT.format(
            from_addr=from_addr,
            subject=subject,
            date=date,
            body=body[:8000],  # Truncate for token limits
        )
        raw = await self._provider.complete(prompt)
        data = _parse_json_safe(raw)
        if data is None or not _validate_json(data, SUMMARY_SCHEMA):
            return None
        return Summary(**data)

    async def generate_drafts(
        self,
        from_addr: str,
        subject: str,
        date: str,
        body: str,
        user_context: str = "",
        num_drafts: int = 3,
    ) -> list[DraftProposal]:
        """Generate draft reply options."""
        prompt = DRAFT_REPLY_PROMPT.format(
            from_addr=from_addr,
            subject=subject,
            date=date,
            body=body[:8000],
            user_context=user_context or "None",
            num_drafts=num_drafts,
        )
        raw = await self._provider.complete(prompt)
        data = _parse_json_safe(raw)
        if data is None or not _validate_json(data, DRAFT_SCHEMA):
            return []
        return [DraftProposal(**d) for d in data["drafts"]]

    async def extract_event(
        self,
        from_addr: str,
        subject: str,
        date: str,
        body: str,
    ) -> EventProposal | None:
        """Extract a calendar event from an email."""
        prompt = EXTRACT_EVENT_PROMPT.format(
            from_addr=from_addr,
            subject=subject,
            date=date,
            body=body[:8000],
        )
        raw = await self._provider.complete(prompt)
        data = _parse_json_safe(raw)
        if data is None or not _validate_json(data, EVENT_SCHEMA):
            return None
        if data.get("title") is None:
            return None
        return EventProposal(**data)


_ai_service: AIService | None = None


def get_ai_service(settings: Settings) -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService(settings)
    return _ai_service

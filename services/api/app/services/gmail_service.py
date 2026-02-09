"""Gmail API integration service."""

import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import Settings
from app.services.crypto_service import CryptoService

logger = logging.getLogger(__name__)


class GmailService:
    """Service for interacting with Gmail API."""

    def __init__(self, settings: Settings, crypto: CryptoService) -> None:
        self._settings = settings
        self._crypto = crypto

    def _get_credentials(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: bytes,
    ) -> Credentials:
        """Build Google credentials from encrypted tokens."""
        access_token = self._crypto.decrypt(encrypted_access_token)
        refresh_token = self._crypto.decrypt(encrypted_refresh_token)
        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._settings.google_client_id,
            client_secret=self._settings.google_client_secret.get_secret_value(),
        )

    def _build_service(self, credentials: Credentials):
        """Build Gmail API service."""
        return build("gmail", "v1", credentials=credentials)

    async def setup_watch(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: bytes,
    ) -> dict[str, Any]:
        """Set up Gmail push notifications via Pub/Sub.

        Returns the watch response containing historyId and expiration.
        """
        creds = self._get_credentials(encrypted_access_token, encrypted_refresh_token)
        service = self._build_service(creds)

        # Run in executor since google-api-python-client is synchronous
        import asyncio

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: (
                service.users()
                .watch(
                    userId="me",
                    body={
                        "topicName": self._settings.google_pubsub_topic,
                        "labelIds": ["INBOX"],
                    },
                )
                .execute()
            ),
        )
        logger.info("Gmail watch set up, historyId=%s", response.get("historyId"))
        return response

    async def get_history(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: bytes,
        start_history_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch message history since a given historyId.

        Returns list of history records containing messagesAdded.
        """
        creds = self._get_credentials(encrypted_access_token, encrypted_refresh_token)
        service = self._build_service(creds)

        import asyncio

        loop = asyncio.get_event_loop()

        all_history: list[dict[str, Any]] = []
        page_token = None

        while True:
            params: dict[str, Any] = {
                "userId": "me",
                "startHistoryId": start_history_id,
                "historyTypes": ["messageAdded"],
            }
            if page_token:
                params["pageToken"] = page_token

            response = await loop.run_in_executor(
                None,
                lambda p=params: service.users().history().list(**p).execute(),
            )

            history = response.get("history", [])
            all_history.extend(history)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return all_history

    async def get_message(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: bytes,
        message_id: str,
    ) -> dict[str, Any]:
        """Fetch a single message by ID with full payload."""
        creds = self._get_credentials(encrypted_access_token, encrypted_refresh_token)
        service = self._build_service(creds)

        import asyncio

        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            lambda: (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            ),
        )

    async def get_thread(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: bytes,
        thread_id: str,
    ) -> dict[str, Any]:
        """Fetch an entire thread by ID with full message payloads."""
        creds = self._get_credentials(encrypted_access_token, encrypted_refresh_token)
        service = self._build_service(creds)

        import asyncio

        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            lambda: (
                service.users()
                .threads()
                .get(
                    userId="me",
                    id=thread_id,
                    format="full",
                )
                .execute()
            ),
        )

    async def list_sent_messages(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: bytes,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Fetch recent sent messages for style detection."""
        creds = self._get_credentials(encrypted_access_token, encrypted_refresh_token)
        service = self._build_service(creds)

        import asyncio

        loop = asyncio.get_event_loop()

        # List message IDs from SENT label
        list_response = await loop.run_in_executor(
            None,
            lambda: (
                service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=["SENT"],
                    maxResults=max_results,
                )
                .execute()
            ),
        )

        message_ids = [m["id"] for m in list_response.get("messages", [])]

        # Fetch full messages
        messages: list[dict[str, Any]] = []
        for mid in message_ids:
            msg = await loop.run_in_executor(
                None,
                lambda m=mid: (
                    service.users()
                    .messages()
                    .get(userId="me", id=m, format="full")
                    .execute()
                ),
            )
            messages.append(msg)

        return messages

    async def create_draft(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: bytes,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
    ) -> dict[str, Any]:
        """Create a Gmail draft (NEVER sends automatically).

        Returns the created draft resource.
        """
        import base64
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

        draft_body: dict[str, Any] = {
            "message": {"raw": raw},
        }
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        creds = self._get_credentials(encrypted_access_token, encrypted_refresh_token)
        service = self._build_service(creds)

        import asyncio

        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            lambda: (
                service.users()
                .drafts()
                .create(
                    userId="me",
                    body=draft_body,
                )
                .execute()
            ),
        )


def get_gmail_service(settings: Settings, crypto: CryptoService) -> GmailService:
    return GmailService(settings, crypto)

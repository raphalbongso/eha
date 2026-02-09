"""Gmail webhook router for Pub/Sub push notifications."""

import base64
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt as jose_jwt

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gmail", tags=["gmail"])


def _verify_pubsub_token(request: Request, settings: Settings) -> dict | None:
    """Verify Google Pub/Sub push JWT bearer token.

    Google Pub/Sub sends a JWT in the Authorization header.
    We validate it to ensure the webhook is from Google.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]

    # For development, accept a simple verification token
    verification_token = settings.google_pubsub_verification_token.get_secret_value()
    if verification_token and token == verification_token:
        return {"verified": True}

    # In production, verify the Google-signed JWT
    # This requires fetching Google's public keys and validating
    # For now, we accept if the token matches our verification token
    logger.warning("Pub/Sub JWT verification not fully implemented for production")
    return None


@router.post("/webhook")
async def gmail_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    """Receive Gmail push notification from Google Pub/Sub.

    Flow:
    1. Google Pub/Sub sends POST with notification
    2. We extract historyId from the notification
    3. We enqueue a Celery task to process the history
    """
    # Verify the request is from Google Pub/Sub
    verified = _verify_pubsub_token(request, settings)
    if not verified:
        # In development mode, allow unverified requests
        if settings.app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Pub/Sub token",
            )
        logger.warning("Accepting unverified Pub/Sub webhook in %s mode", settings.app_env)

    body = await request.json()

    # Pub/Sub message format:
    # {
    #   "message": {
    #     "data": "<base64 encoded>",
    #     "messageId": "...",
    #     "publishTime": "..."
    #   },
    #   "subscription": "..."
    # }
    message = body.get("message", {})
    data_b64 = message.get("data", "")

    if not data_b64:
        logger.warning("Empty Pub/Sub message data")
        # Return 200 to acknowledge (prevent retries for empty messages)
        return {"status": "ok", "detail": "empty message"}

    try:
        data = json.loads(base64.b64decode(data_b64))
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to decode Pub/Sub data: %s", e)
        return {"status": "ok", "detail": "invalid data"}

    # Gmail notification data:
    # {"emailAddress": "user@gmail.com", "historyId": "123456"}
    email_address = data.get("emailAddress")
    history_id = data.get("historyId")

    if not email_address or not history_id:
        logger.warning("Missing emailAddress or historyId in webhook data")
        return {"status": "ok", "detail": "missing fields"}

    logger.info("Gmail webhook: email=%s historyId=%s", email_address[:3] + "***", history_id)

    # Enqueue Celery task for async processing
    from app.tasks.gmail_tasks import process_gmail_notification

    process_gmail_notification.delay(email_address=email_address, history_id=str(history_id))

    return {"status": "ok"}

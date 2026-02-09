"""Gmail webhook router for Pub/Sub push notifications."""

import base64
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gmail", tags=["gmail"])


def _verify_pubsub_jwt(token: str, settings: Settings) -> dict | None:
    """Verify a Google Pub/Sub push JWT using Google's public keys.

    Returns the decoded claims on success, None on failure.
    """
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=None,
        )
        # Verify the issuer is Google's accounts service
        issuer = claims.get("iss", "")
        if issuer not in ("accounts.google.com", "https://accounts.google.com"):
            logger.warning("Pub/Sub JWT has unexpected issuer: %s", issuer)
            return None
        # Optionally verify the email matches a known service account
        email = claims.get("email", "")
        if email and not email.endswith(".iam.gserviceaccount.com"):
            logger.warning("Pub/Sub JWT email is not a service account: %s", email[:10] + "***")
            return None
        return claims
    except Exception as e:
        logger.warning("Pub/Sub JWT verification failed: %s", e)
        return None


def _verify_pubsub_token(request: Request, settings: Settings) -> dict | None:
    """Verify Google Pub/Sub push authorization.

    Supports:
    1. Simple verification token (development)
    2. Full JWT verification via Google's public keys (production)
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]

    # Dev mode: accept simple verification token
    verification_token = settings.google_pubsub_verification_token.get_secret_value()
    if verification_token and token == verification_token:
        return {"verified": True, "mode": "token"}

    # Production: verify Google-signed JWT
    claims = _verify_pubsub_jwt(token, settings)
    if claims:
        return {"verified": True, "mode": "jwt", "email": claims.get("email")}

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

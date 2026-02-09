"""Authentication routes: Google OAuth PKCE flow + JWT session tokens."""

import base64
import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_current_user_id, get_db
from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthCallbackRequest,
    GoogleAuthStartResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from app.services.crypto_service import get_crypto_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "openid",
    "email",
    "profile",
]

# PKCE state TTL: 10 minutes
_PKCE_STATE_TTL = 600
_redis_client: aioredis.Redis | None = None


async def _get_redis(settings: Settings) -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def _store_pkce_state(state: str, data: dict, settings: Settings) -> None:
    """Store PKCE state in Redis with TTL."""
    r = await _get_redis(settings)
    key = f"pkce:{state}"
    await r.set(key, json.dumps(data), ex=_PKCE_STATE_TTL)


async def _pop_pkce_state(state: str, settings: Settings) -> dict | None:
    """Atomically retrieve and delete PKCE state from Redis."""
    r = await _get_redis(settings)
    key = f"pkce:{state}"
    pipe = r.pipeline()
    pipe.get(key)
    pipe.delete(key)
    results = await pipe.execute()
    raw = results[0]
    if raw is None:
        return None
    return json.loads(raw)


def _create_jwt(
    user_id: str,
    token_type: str,
    settings: Settings,
    ttl: timedelta,
) -> str:
    """Create a JWT token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(
        payload,
        settings.jwt_private_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


@router.post("/google/start", response_model=GoogleAuthStartResponse)
async def google_auth_start(settings: Settings = Depends(get_settings)):
    """Start Google OAuth PKCE flow. Returns auth URL and state."""
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)

    # Store state → code_verifier in Redis
    await _store_pkce_state(
        state,
        {"code_verifier": code_verifier, "created_at": datetime.now(timezone.utc).isoformat()},
        settings,
    )

    # Build code_challenge (S256)
    code_challenge = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge_b64 = base64.urlsafe_b64encode(code_challenge).rstrip(b"=").decode("ascii")

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": code_challenge_b64,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return GoogleAuthStartResponse(auth_url=auth_url, state=state)


@router.post("/google/callback", response_model=TokenResponse)
async def google_auth_callback(
    body: GoogleAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Exchange authorization code for tokens. Creates/updates user."""
    import httpx

    # Verify state from Redis (atomic pop)
    pending = await _pop_pkce_state(body.state, settings)
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Exchange code for Google tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "code": body.code,
                "code_verifier": body.code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            },
        )

    if token_response.status_code != 200:
        logger.error("Google token exchange failed: %s", token_response.text)
        raise HTTPException(status_code=400, detail="Token exchange failed")

    token_data = token_response.json()
    google_access_token = token_data["access_token"]
    google_refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    # Fetch user info
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
        )

    if userinfo_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")

    userinfo = userinfo_response.json()
    google_id = userinfo["id"]
    email = userinfo["email"]
    name = userinfo.get("name", email)

    # Upsert user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(google_id=google_id, email=email, name=name)
        db.add(user)
        await db.flush()

    # Encrypt and store Google tokens
    crypto = get_crypto_service(settings)
    encrypted_access = crypto.encrypt(google_access_token)
    encrypted_refresh = crypto.encrypt(google_refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Upsert OAuth token
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user.id))
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        oauth_token.encrypted_access_token = encrypted_access
        oauth_token.encrypted_refresh_token = encrypted_refresh
        oauth_token.expires_at = expires_at
        oauth_token.scopes = " ".join(SCOPES)
    else:
        oauth_token = OAuthToken(
            user_id=user.id,
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            expires_at=expires_at,
            scopes=" ".join(SCOPES),
        )
        db.add(oauth_token)

    await db.flush()

    # Generate EHA JWT tokens
    access_token = _create_jwt(
        str(user.id),
        "access",
        settings,
        timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    )
    refresh_token = _create_jwt(
        str(user.id),
        "refresh",
        settings,
        timedelta(days=settings.jwt_refresh_token_ttl_days),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_ttl_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshTokenRequest,
    settings: Settings = Depends(get_settings),
):
    """Refresh an expired access token."""
    from jose import JWTError

    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.jwt_private_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = _create_jwt(
        user_id,
        "access",
        settings,
        timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    )
    new_refresh = _create_jwt(
        user_id,
        "refresh",
        settings,
        timedelta(days=settings.jwt_refresh_token_ttl_days),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.jwt_access_token_ttl_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(id=str(user.id), email=user.email, name=user.name)

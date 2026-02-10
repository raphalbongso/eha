"""Auth request/response schemas."""

from pydantic import BaseModel


class GoogleAuthStartResponse(BaseModel):
    auth_url: str
    state: str


class GoogleAuthCallbackRequest(BaseModel):
    code: str
    state: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str

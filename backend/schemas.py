"""Pydantic models for EcoQuery API."""

import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    # Unbounded before: a client could ship a multi-megabyte id that is only
    # ever compared against a short model list.
    model_id: Optional[str] = Field(default=None, max_length=200)
    images: Optional[List[str]] = Field(default=None, max_length=3)  # Base64 encoded images
    conversation: Optional[List[dict]] = Field(default=None, max_length=20)
    max_output_tokens: Optional[int] = Field(default=None, ge=1, le=4000)
    routing_mode: Optional[str] = Field(default="balanced")

    @field_validator('routing_mode')
    @classmethod
    def validate_routing_mode(cls, value):
        if value is None:
            return "balanced"
        aliases = {"performance": "fast", "budget": "low-cost"}
        normalized = aliases.get(value.lower(), value.lower())
        if normalized not in {"green", "balanced", "quality", "fast", "low-cost"}:
            raise ValueError('routing_mode must be green, balanced, quality, fast, or low-cost')
        return normalized

    @field_validator('conversation')
    @classmethod
    def validate_conversation(cls, conversation):
        """History is forwarded verbatim to the model, so it is attacker-controlled.

        `system` is deliberately not an allowed role: the frontend already
        strips it, and accepting one would let an anonymous caller append a
        second system prompt after EcoQuery's own. Unknown keys are dropped so
        nothing outside `role`/`content` can reach the provider API.
        """
        if not conversation:
            return conversation
        cleaned = []
        for item in conversation:
            if not isinstance(item, dict):
                raise ValueError('conversation entries must be objects')
            role = item.get('role')
            if role not in ('user', 'assistant'):
                raise ValueError("conversation roles must be 'user' or 'assistant'")
            content = item.get('content')
            if not isinstance(content, str) or not content.strip():
                raise ValueError('conversation content must be a non-empty string')
            if len(content) > 4000:
                raise ValueError('conversation entries must be 4000 characters or fewer')
            cleaned.append({'role': role, 'content': content})
        return cleaned

    @field_validator('images')
    @classmethod
    def validate_images(cls, images):
        max_base64_chars = 7_000_000  # approximately 5 MB decoded
        if images and any(len(image) > max_base64_chars for image in images):
            raise ValueError('Each image must be 5 MB or smaller')
        return images


class ChatResponse(BaseModel):
    reply: str
    metadata: dict


class SignupRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not EMAIL_REGEX.match(v):
            raise ValueError('Invalid email format')
        return v.lower()


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return v.lower()


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UpdateNameRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)


class UpdatePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class DeleteAccountRequest(BaseModel):
    password: str = Field(default="", min_length=0, max_length=128)


class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class OrgInviteRequest(BaseModel):
    email: str = Field(..., max_length=254)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not EMAIL_REGEX.match(v):
            raise ValueError('Invalid email format')
        return v.lower()


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    # Was an untyped `list[str]` with a mutable default: unbounded in size and
    # free to carry arbitrary strings into the stored subscription.
    events: List[str] = Field(default=["query.routed"], max_length=10)

    @field_validator('events')
    @classmethod
    def validate_events(cls, v):
        allowed = {"query.routed"}
        unknown = [e for e in v if e not in allowed]
        if unknown:
            raise ValueError(f'Unsupported webhook events: {", ".join(unknown[:3])}')
        if not v:
            raise ValueError('At least one webhook event is required')
        return v

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        if any(blocked in v for blocked in ['localhost', '127.0.0.1', '0.0.0.0', '10.', '172.', '192.168.']):
            raise ValueError('Private/internal URLs are not allowed')
        return v


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=254)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return v.lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=2048)
    new_password: str = Field(..., min_length=6, max_length=128)


class VerifyOTPRequest(BaseModel):
    email: str = Field(..., max_length=254)
    otp: str = Field(..., min_length=6, max_length=6)


class VerifyEmailRequest(BaseModel):
    email: str = Field(..., max_length=254)
    token: str = Field(..., min_length=1, max_length=2048)


class ResendEmailRequest(BaseModel):
    email: str = Field(..., max_length=254)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return v.lower()

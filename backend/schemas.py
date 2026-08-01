"""Pydantic models for EcoQuery API."""

import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    model_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    metadata: dict


class SignupRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not EMAIL_REGEX.match(v):
            raise ValueError('Invalid email format')
        return v.lower()


class LoginRequest(BaseModel):
    email: str
    password: str

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
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


class DeleteAccountRequest(BaseModel):
    password: str = Field(default="", min_length=0)


class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class OrgInviteRequest(BaseModel):
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not EMAIL_REGEX.match(v):
            raise ValueError('Invalid email format')
        return v.lower()


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., min_length=1)
    events: list[str] = ["query.routed"]

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        if any(blocked in v for blocked in ['localhost', '127.0.0.1', '0.0.0.0', '10.', '172.', '192.168.']):
            raise ValueError('Private/internal URLs are not allowed')
        return v


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return v.lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class AdminUserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str = Field(..., min_length=6, max_length=6)


class VerifyEmailRequest(BaseModel):
    email: str
    token: str


class ResendEmailRequest(BaseModel):
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return v.lower()

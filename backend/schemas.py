"""Pydantic models for EcoQuery API."""

import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    model_id: Optional[str] = None
    images: Optional[List[str]] = Field(default=None, max_length=3)  # Base64 encoded images
    files: Optional[List[dict]] = Field(default=None, max_length=3)  # [{name, content_type, data}]
    conversation: Optional[List[dict]] = Field(default=None, max_length=20)
    max_output_tokens: Optional[int] = Field(default=None, ge=1, le=4000)

    @field_validator('images')
    @classmethod
    def validate_images(cls, images):
        max_base64_chars = 7_000_000  # approximately 5 MB decoded
        if images and any(len(image) > max_base64_chars for image in images):
            raise ValueError('Each image must be 5 MB or smaller')
        return images

    @field_validator('files')
    @classmethod
    def validate_files(cls, files):
        max_base64_chars = 7_000_000
        if files:
            for file in files:
                data = file.get('data', '') if isinstance(file, dict) else ''
                if not isinstance(data, str) or len(data) > max_base64_chars:
                    raise ValueError('Each file must contain data no larger than 5 MB')
        return files


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
    url: str = Field(..., min_length=1, max_length=2000)
    events: list[str] = ["query.routed"]

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        from urllib.parse import urlparse
        try:
            parsed = urlparse(v)
        except Exception:
            raise ValueError('Invalid URL')
        if parsed.scheme not in ('http', 'https'):
            raise ValueError('URL must start with http:// or https://')
        host = (parsed.hostname or '').lower()
        if not host:
            raise ValueError('URL must include a hostname')
        if host in ('localhost', '0.0.0.0', '::1') or host.endswith('.local') or host.endswith('.internal'):
            raise ValueError('Private/internal URLs are not allowed')
        import ipaddress
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip is not None and not ip.is_global:
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

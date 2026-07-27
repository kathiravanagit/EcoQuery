"""Pydantic models for EcoQuery API."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    model_id: Optional[str] = None
    mode: Optional[str] = Field(default="eco", pattern="^(eco|performance)$")


class ChatResponse(BaseModel):
    reply: str
    metadata: dict


class SignupRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    email: str
    password: str


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


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., min_length=1)
    events: list[str] = ["query.routed"]


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class AdminUserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

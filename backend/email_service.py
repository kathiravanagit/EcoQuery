"""
Email Service — uses Resend API for transactional emails.
Sends: confirmation, OTP, password reset, org invites.
"""

import os
import logging
import secrets
import httpx
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("EcoQuery.email")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@ecoquery.app")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://eco2query.vercel.app")
OTP_EXPIRY_MINUTES = 10
RESET_EXPIRY_MINUTES = 60


class EmailService:
    def __init__(self):
        self.api_key = RESEND_API_KEY
        self.from_email = FROM_EMAIL
        self.frontend_url = FRONTEND_URL
        self._available = bool(self.api_key)

    @property
    def available(self):
        return self._available

    async def _send_resend(self, to: str, subject: str, html: str) -> bool:
        """Send email via Resend API."""
        if not self._available:
            logger.info(f"[EMAIL MOCK] To: {to} | Subject: {subject}")
            return True

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self.from_email,
                        "to": [to],
                        "subject": subject,
                        "html": html,
                    },
                )
                response.raise_for_status()
                logger.info(f"Email sent to {to}: {subject}")
                return True
        except Exception as e:
            logger.warning(f"Failed to send email to {to}: {e}")
            return False

    # ── Confirmation Email (after signup) ──────────────────────────────────

    async def send_confirmation(self, to: str, token: str) -> bool:
        """Send email confirmation after signup."""
        link = f"{self.frontend_url}/verify-email?token={token}"
        logo_url = f"{self.frontend_url}/logo.png"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <div style="text-align:center;padding:20px 0;">
                <img src="{logo_url}" alt="EcoQuery" width="48" height="48" style="border-radius:8px;">
            </div>
            <div style="background:#00d46a;color:#000;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:24px;">Welcome to EcoQuery</h1>
            </div>
            <div style="background:#1a1a2e;color:#e0e0e0;padding:30px;border-radius:0 0 12px 12px;">
                <h2 style="color:#00d46a;">Confirm your email</h2>
                <p>Thanks for signing up! Click the button below to verify your email address.</p>
                <a href="{link}" style="display:inline-block;padding:14px 28px;background:#00d46a;color:#000;text-decoration:none;border-radius:8px;font-weight:bold;margin:16px 0;">Verify Email</a>
                <p style="color:#888;font-size:14px;">This link expires in 24 hours.</p>
                <p style="color:#888;font-size:14px;">If you didn't create an account, ignore this email.</p>
            </div>
        </div>
        """
        return await self._send_resend(to, "EcoQuery - Confirm your email", html)

    # ── OTP Email (forgot password) ───────────────────────────────────────

    async def send_otp(self, to: str, otp: str, purpose: str = "password reset") -> bool:
        """Send OTP code to email."""
        logo_url = f"{self.frontend_url}/logo.png"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <div style="text-align:center;padding:20px 0;">
                <img src="{logo_url}" alt="EcoQuery" width="48" height="48" style="border-radius:8px;">
            </div>
            <div style="background:#00d46a;color:#000;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:24px;">EcoQuery Verification</h1>
            </div>
            <div style="background:#1a1a2e;color:#e0e0e0;padding:30px;border-radius:0 0 12px 12px;">
                <h2 style="color:#00d46a;">Your OTP Code</h2>
                <p>Use this code to complete your {purpose}:</p>
                <div style="background:#0a0a1a;border:2px solid #00d46a;border-radius:8px;padding:20px;text-align:center;margin:16px 0;">
                    <span style="font-size:36px;font-weight:bold;color:#00d46a;letter-spacing:8px;">{otp}</span>
                </div>
                <p style="color:#888;font-size:14px;">This code expires in {OTP_EXPIRY_MINUTES} minutes.</p>
                <p style="color:#888;font-size:14px;">If you didn't request this, ignore this email.</p>
            </div>
        </div>
        """
        return await self._send_resend(to, f"EcoQuery - Your {purpose} code", html)

    # ── Password Reset Link ───────────────────────────────────────────────

    async def send_password_reset(self, to: str, token: str) -> bool:
        """Send password reset link."""
        link = f"{self.frontend_url}/reset-password?token={token}"
        logo_url = f"{self.frontend_url}/logo.png"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <div style="text-align:center;padding:20px 0;">
                <img src="{logo_url}" alt="EcoQuery" width="48" height="48" style="border-radius:8px;">
            </div>
            <div style="background:#00d46a;color:#000;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:24px;">EcoQuery Password Reset</h1>
            </div>
            <div style="background:#1a1a2e;color:#e0e0e0;padding:30px;border-radius:0 0 12px 12px;">
                <h2 style="color:#00d46a;">Reset your password</h2>
                <p>Click the button below to create a new password.</p>
                <a href="{link}" style="display:inline-block;padding:14px 28px;background:#00d46a;color:#000;text-decoration:none;border-radius:8px;font-weight:bold;margin:16px 0;">Reset Password</a>
                <p style="color:#888;font-size:14px;">This link expires in {RESET_EXPIRY_MINUTES} minutes.</p>
                <p style="color:#888;font-size:14px;">If you didn't request this, ignore this email.</p>
            </div>
        </div>
        """
        return await self._send_resend(to, "EcoQuery - Password Reset", html)

    # ── Org Invite ────────────────────────────────────────────────────────

    async def send_org_invite(self, to: str, org_name: str, invited_by: str, token: str) -> bool:
        """Send organization invitation."""
        link = f"{self.frontend_url}/join-org?token={token}"
        logo_url = f"{self.frontend_url}/logo.png"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <div style="text-align:center;padding:20px 0;">
                <img src="{logo_url}" alt="EcoQuery" width="48" height="48" style="border-radius:8px;">
            </div>
            <div style="background:#00d46a;color:#000;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:24px;">You're Invited!</h1>
            </div>
            <div style="background:#1a1a2e;color:#e0e0e0;padding:30px;border-radius:0 0 12px 12px;">
                <h2 style="color:#00d46a;">Join {org_name}</h2>
                <p><strong>{invited_by}</strong> invited you to join <strong>{org_name}</strong> on EcoQuery.</p>
                <a href="{link}" style="display:inline-block;padding:14px 28px;background:#00d46a;color:#000;text-decoration:none;border-radius:8px;font-weight:bold;margin:16px 0;">Join Organization</a>
                <p style="color:#888;font-size:14px;">Collaborate on carbon-aware AI routing with your team.</p>
            </div>
        </div>
        """
        return await self._send_resend(to, f"EcoQuery - Join {org_name}", html)


# ── OTP Store (in-memory + MongoDB) ────────────────────────────────────────

class OTPStore:
    """Stores OTPs in memory with expiry."""

    def __init__(self):
        self._store: dict = {}  # email -> {otp, purpose, expires_at}

    def generate(self, email: str, purpose: str = "password reset") -> str:
        """Generate and store OTP."""
        otp = f"{secrets.randbelow(900000) + 100000}"  # 6-digit OTP
        self._store[email] = {
            "otp": otp,
            "purpose": purpose,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
        }
        return otp

    def verify(self, email: str, otp: str) -> bool:
        """Verify OTP and delete if valid."""
        record = self._store.get(email)
        if not record:
            return False
        if record["expires_at"] < datetime.now(timezone.utc):
            del self._store[email]
            return False
        if record["otp"] != otp:
            return False
        del self._store[email]
        return True

    def cleanup(self):
        """Remove expired OTPs."""
        now = datetime.now(timezone.utc)
        expired = [k for k, v in self._store.items() if v["expires_at"] < now]
        for k in expired:
            del self._store[k]


email_service = EmailService()
otp_store = OTPStore()

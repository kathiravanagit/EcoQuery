import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("EcoQuery.email")

class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASS", "")
        self.from_addr = os.getenv("SMTP_FROM", "noreply@ecoquery.app")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        self._available = bool(self.smtp_host and self.smtp_user and self.smtp_pass)

    @property
    def available(self):
        return self._available

    async def send(self, to: str, subject: str, html: str, text: str = ""):
        if not self._available:
            logger.info(f"[EMAIL MOCK] To: {to} | Subject: {subject}\n{text or html}")
            return True
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = to
            if text:
                msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_addr, [to], msg.as_string())
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send email to {to}: {e}")
            return False

    async def send_password_reset(self, to: str, token: str):
        link = f"{self.frontend_url}/reset-password?token={token}"
        text = f"Reset your EcoQuery password: {link}"
        html = f"""
        <h2>EcoQuery Password Reset</h2>
        <p>Click the link below to reset your password. This link expires in 1 hour.</p>
        <a href="{link}" style="display:inline-block;padding:12px 24px;background:#00d46a;color:#000;text-decoration:none;border-radius:8px;">Reset Password</a>
        <p style="margin-top:16px;color:#888;">If you didn't request this, ignore this email.</p>
        """
        return await self.send(to, "EcoQuery — Password Reset", html, text)

    async def send_org_invite(self, to: str, org_name: str, invited_by: str, token: str):
        link = f"{self.frontend_url}/join-org?token={token}"
        text = f"{invited_by} invited you to join {org_name} on EcoQuery: {link}"
        html = f"""
        <h2>You're Invited!</h2>
        <p><strong>{invited_by}</strong> invited you to join <strong>{org_name}</strong> on EcoQuery.</p>
        <a href="{link}" style="display:inline-block;padding:12px 24px;background:#00d46a;color:#000;text-decoration:none;border-radius:8px;">Join Organization</a>
        <p style="margin-top:16px;color:#888;">Collaborate on carbon-aware AI routing with your team.</p>
        """
        return await self.send(to, f"EcoQuery — Join {org_name}", html, text)

email_service = EmailService()

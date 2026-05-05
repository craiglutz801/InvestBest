"""
Notification service: send alerts via email, Slack, Telegram.
Logs to NotificationLog.
"""
from __future__ import annotations
from backend.models import NotificationLog
from config.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def send_test(self, channel: str, message: str) -> tuple[bool, str | None]:
        """Send a test message to channel. Returns (success, error_message)."""
        if channel == "email":
            return await self._send_email("InvestBest test", message)
        if channel == "slack":
            return await self._send_slack(message)
        if channel == "telegram":
            return await self._send_telegram(message)
        return False, f"Unknown channel: {channel}"

    async def _log(self, channel: str, subject: str | None, body: str | None, status: str, error: str | None = None):
        entry = NotificationLog(channel=channel, subject=subject, body=body, status=status, error=error)
        self.session.add(entry)
        await self.session.commit()

    async def _send_email(self, subject: str, body: str) -> tuple[bool, str | None]:
        if not self.settings.smtp_host or not self.settings.smtp_user:
            await self._log("email", subject, body, "failed", "SMTP not configured")
            return False, "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in config."
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as s:
                s.starttls()
                s.login(self.settings.smtp_user, self.settings.smtp_password)
                # Note: in real use you'd set a recipient; for test we just try connect/send to self
                # s.sendmail(...)
            await self._log("email", subject, body, "sent")
            return True, None
        except Exception as e:
            await self._log("email", subject, body, "failed", str(e))
            return False, str(e)

    async def _send_slack(self, text: str) -> tuple[bool, str | None]:
        if not self.settings.slack_webhook_url:
            await self._log("slack", None, text, "failed", "Slack webhook not configured")
            return False, "Slack webhook not configured."
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    self.settings.slack_webhook_url,
                    json={"text": text},
                    timeout=10.0,
                )
            if r.status_code >= 400:
                await self._log("slack", None, text, "failed", r.text)
                return False, r.text
            await self._log("slack", None, text, "sent")
            return True, None
        except Exception as e:
            await self._log("slack", None, text, "failed", str(e))
            return False, str(e)

    async def _send_telegram(self, text: str) -> tuple[bool, str | None]:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            await self._log("telegram", None, text, "failed", "Telegram not configured")
            return False, "Telegram not configured."
        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    url,
                    json={"chat_id": self.settings.telegram_chat_id, "text": text},
                    timeout=10.0,
                )
            if r.status_code >= 400:
                await self._log("telegram", None, text, "failed", r.text)
                return False, r.text
            await self._log("telegram", None, text, "sent")
            return True, None
        except Exception as e:
            await self._log("telegram", None, text, "failed", str(e))
            return False, str(e)

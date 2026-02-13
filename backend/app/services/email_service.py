"""SMTP-based email sending service."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Send transactional emails via SMTP."""

    def send(
        self,
        to: str,
        subject: str,
        body_html: str,
        from_addr: str | None = None,
    ) -> bool:
        """Send an HTML email. Returns ``True`` on success."""
        if not settings.NOTIFICATION_ENABLED:
            logger.info("Notifications disabled — skipping email to %s", to)
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr or settings.SMTP_USERNAME
        msg["To"] = to
        msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                if settings.SMTP_PORT != 25:
                    server.starttls()
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [to], msg.as_string())
            logger.info("Email sent to %s: %s", to, subject)
            return True
        except Exception:
            logger.exception("Failed to send email to %s", to)
            return False

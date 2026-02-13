"""Template-based notification service."""

from __future__ import annotations

import logging
from enum import Enum

from backend.app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    LOW_STOCK_ALERT = "LOW_STOCK_ALERT"
    PAYMENT_OVERDUE = "PAYMENT_OVERDUE"
    FISCAL_CLOSE_REMINDER = "FISCAL_CLOSE_REMINDER"
    REPORT_READY = "REPORT_READY"


_TEMPLATES: dict[NotificationType, dict[str, str]] = {
    NotificationType.LOW_STOCK_ALERT: {
        "subject": "Low Stock Alert: {product_name}",
        "body": (
            "<h2>Low Stock Alert</h2>"
            "<p>Product <strong>{product_name}</strong> has fallen below the "
            "reorder point. Current quantity: <strong>{quantity}</strong>.</p>"
        ),
    },
    NotificationType.PAYMENT_OVERDUE: {
        "subject": "Payment Overdue: Invoice #{invoice_number}",
        "body": (
            "<h2>Payment Overdue</h2>"
            "<p>Invoice <strong>#{invoice_number}</strong> for "
            "<strong>{amount}</strong> SAR is overdue since {due_date}.</p>"
        ),
    },
    NotificationType.FISCAL_CLOSE_REMINDER: {
        "subject": "Fiscal Period Close Reminder",
        "body": (
            "<h2>Fiscal Period Close Reminder</h2>"
            "<p>The fiscal period ending <strong>{period_end}</strong> is "
            "approaching. Please review and close the period.</p>"
        ),
    },
    NotificationType.REPORT_READY: {
        "subject": "Report Ready: {report_type}",
        "body": (
            "<h2>Report Ready</h2>"
            "<p>Your <strong>{report_type}</strong> report has been generated "
            "and is ready for download.</p>"
        ),
    },
}


class NotificationService:
    """Send typed notifications using predefined templates."""

    def __init__(self) -> None:
        self._email = EmailService()

    def send(
        self,
        notification_type: NotificationType,
        recipient_email: str,
        **kwargs: str,
    ) -> bool:
        """Render the template for *notification_type* and send via email."""
        template = _TEMPLATES.get(notification_type)
        if template is None:
            logger.error("Unknown notification type: %s", notification_type)
            return False

        subject = template["subject"].format(**kwargs)
        body = template["body"].format(**kwargs)
        return self._email.send(to=recipient_email, subject=subject, body_html=body)

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from .config import EMAIL_FROM_ADDRESS, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME


class EmailComposer:
    def compose(self, complaint_json: dict[str, Any], recipient_email: str, recipient_name: str) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = f"Civic complaint for {complaint_json.get('location', 'unknown location')}"
        message["From"] = EMAIL_FROM_ADDRESS or SMTP_USERNAME
        message["To"] = recipient_email
        body = (
            f"Dear {recipient_name},\n\n"
            f"Issue: {complaint_json.get('issue_text', '')}\n"
            f"Location: {complaint_json.get('location', '')}\n"
            f"Ward: {complaint_json.get('location_data', {}).get('ward', '')}\n"
            f"Policy deadline (hours): {complaint_json.get('policy_deadline_hours')}\n"
            f"User duration (hours): {complaint_json.get('user_duration_hours')}\n"
            f"Consistency: {'consistent' if not complaint_json.get('is_violation') else 'inconsistent'}\n\n"
            f"Policy excerpt:\n{complaint_json.get('retrieved_policy', '')}\n\n"
            f"Recommended action:\n{complaint_json.get('recommended_action', '')}\n"
        )
        message.set_content(body)
        return message


class EmailSender:
    @property
    def enabled(self) -> bool:
        return bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD and EMAIL_FROM_ADDRESS)

    def send(self, message: EmailMessage) -> tuple[bool, str]:
        if not self.enabled:
            return False, "SMTP is not configured."

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return True, "Email sent successfully."

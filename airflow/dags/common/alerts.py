"""Failure alerts shared by Airflow DAGs."""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

LOGGER = logging.getLogger(__name__)


def notify_failure(context: dict[str, Any]) -> None:
    """Log a final task failure and optionally notify by Gmail."""
    task_instance = context.get("task_instance")
    exception = context.get("exception")
    dag_id = context.get("dag").dag_id if context.get("dag") else "unknown"
    task_id = task_instance.task_id if task_instance else "unknown"
    message = (
        f"Airflow task failed: dag={dag_id}, "
        f"task={task_id}, "
        f"run_id={context.get('run_id')}, error={exception}"
    )
    LOGGER.error(message)

    sender = os.getenv("ALERT_EMAIL_FROM", "").strip()
    recipient = os.getenv("ALERT_EMAIL_TO", "").strip()
    app_password = os.getenv("ALERT_EMAIL_APP_PASSWORD", "").strip().replace(" ", "")
    email_settings = (sender, recipient, app_password)
    if not any(email_settings):
        return
    if not all(email_settings):
        LOGGER.error(
            "Gmail alert configuration is incomplete; set ALERT_EMAIL_FROM, "
            "ALERT_EMAIL_TO, and ALERT_EMAIL_APP_PASSWORD"
        )
        return

    email = EmailMessage()
    email["Subject"] = f"Airflow task failed: {dag_id}.{task_id}"
    email["From"] = sender
    email["To"] = recipient
    email.set_content(message)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(sender, app_password)
            smtp.send_message(email)
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        LOGGER.error("Could not send Airflow failure email: %s", exc)

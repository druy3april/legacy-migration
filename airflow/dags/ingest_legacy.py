"""Daily incremental ingestion from the legacy SQL Server into the warehouse."""
import logging
import os
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from typing import Any

import pendulum
from airflow.exceptions import AirflowFailException
from airflow.sdk import dag, task

SOURCE_TABLES = ["customers", "products", "orders", "order_items"]
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


@dag(
    dag_id="ingest_legacy",
    schedule="0 1 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_exponential_backoff": True,
        "execution_timeout": timedelta(minutes=10),
        "on_failure_callback": notify_failure,
    },
    tags=["legacy", "ingestion"],
)
def ingest_legacy():
    @task
    def get_upper_bound() -> int:
        from ingest_incremental import read_upper_bound

        return read_upper_bound()

    @task
    def ingest(table: str, upper: int) -> dict[str, str | int | None]:
        from airflow.sdk import get_current_context
        from ingest_incremental import SchemaDriftError, ingest_table

        context = get_current_context()
        try:
            return ingest_table(
                table,
                upper=upper,
                run_id=context["run_id"],
            )
        except SchemaDriftError as exc:
            raise AirflowFailException(str(exc)) from exc

    @task
    def detect_deletes(
        ingestion_results: list[dict[str, str | int | None]],
    ) -> list[dict[str, str | int]]:
        from ingest_incremental import detect_deletes as mark_deleted_rows

        results = []
        for result in ingestion_results:
            table = str(result["table"])
            deleted_count = mark_deleted_rows(table)
            LOGGER.info(
                "Delete detection completed: table=%s deleted=%d",
                table,
                deleted_count,
            )
            results.append({"table": table, "deleted": deleted_count})
        return results

    @task
    def summarize(
        results: list[dict[str, Any]], deletion_results: list[dict[str, Any]]
    ) -> None:
        row_counts = {
            str(result["table"]): int(result["rows"])
            for result in results
        }
        total_rows = sum(row_counts.values())
        deleted_counts = {
            str(result["table"]): int(result["deleted"])
            for result in deletion_results
        }
        LOGGER.info(
            "Ingestion run completed: rows_by_table=%s total_rows=%d "
            "deleted_by_table=%s",
            row_counts,
            total_rows,
            deleted_counts,
        )

    upper = get_upper_bound()
    ingestion_results = ingest.partial(upper=upper).expand(table=SOURCE_TABLES)
    deletion_results = detect_deletes(ingestion_results)
    summarize(ingestion_results, deletion_results)


ingest_legacy()

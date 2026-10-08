"""Daily incremental ingestion from the legacy SQL Server into the warehouse."""
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

import pendulum
from airflow.exceptions import AirflowFailException
from airflow.sdk import dag, task

SOURCE_TABLES = ["customers", "products", "orders", "order_items"]
LOGGER = logging.getLogger(__name__)


def notify_failure(context: dict[str, Any]) -> None:
    """Log a final task failure and optionally notify the configured webhook."""
    task_instance = context.get("task_instance")
    exception = context.get("exception")
    message = (
        f"Airflow task failed: dag={context.get('dag').dag_id if context.get('dag') else 'unknown'}, "
        f"task={task_instance.task_id if task_instance else 'unknown'}, "
        f"run_id={context.get('run_id')}, error={exception}"
    )
    LOGGER.error(message)

    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return

    host = urlsplit(webhook_url).hostname
    payload_key = "content" if host in {"discord.com", "discordapp.com"} else "text"
    payload = json.dumps({payload_key: message}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                LOGGER.error("Failure webhook returned HTTP %s", response.status)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        LOGGER.error("Could not send Airflow failure webhook: %s", exc)


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
    def summarize(results: list[dict[str, Any]]) -> None:
        row_counts = {
            str(result["table"]): int(result["rows"])
            for result in results
        }
        total_rows = sum(row_counts.values())
        LOGGER.info(
            "Ingestion run completed: rows_by_table=%s total_rows=%d",
            row_counts,
            total_rows,
        )

    upper = get_upper_bound()
    ingestion_results = ingest.partial(upper=upper).expand(table=SOURCE_TABLES)
    summarize(ingestion_results)


ingest_legacy()

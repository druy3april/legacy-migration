"""Daily incremental ingestion from the legacy SQL Server into the warehouse."""
import logging
from datetime import timedelta
from typing import Any

import pendulum
from airflow.exceptions import AirflowFailException
from airflow.sdk import dag, task

from common.alerts import notify_failure
from common.assets import WAREHOUSE_RAW

SOURCE_TABLES = ["customers", "products", "orders", "order_items"]
LOGGER = logging.getLogger(__name__)


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
        from ingest_incremental import (
            DeleteGuardError,
            detect_deletes as mark_deleted_rows,
        )

        results = []
        for result in ingestion_results:
            table = str(result["table"])
            try:
                deleted_count = mark_deleted_rows(table)
            except DeleteGuardError as exc:
                raise AirflowFailException(str(exc)) from exc
            LOGGER.info(
                "Delete detection completed: table=%s deleted=%d",
                table,
                deleted_count,
            )
            results.append({"table": table, "deleted": deleted_count})
        return results

    @task(outlets=[WAREHOUSE_RAW])
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

"""Đối soát báo cáo cũ với mart dbt, chạy khi CẢ HAI phía vừa làm mới xong."""

import logging
from datetime import timedelta

import pendulum
from airflow.exceptions import AirflowFailException
from airflow.sdk import dag, task

from common.alerts import notify_failure
from common.assets import LEGACY_REPORTS, WAREHOUSE_MARTS

LOGGER = logging.getLogger(__name__)

# Giữ đồng bộ với reconciliation/specs.py (không import ở top-level để DAG parse nhanh)
REPORTS = [
    "daily_revenue",
    "customer_ltv",
    "customer_segments",
    "product_sales",
    "cumulative_revenue",
    "top_products_by_category",
    "category_monthly_revenue",
]


@dag(
    dag_id="reconciliation",
    schedule=(WAREHOUSE_MARTS & LEGACY_REPORTS),
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
        "execution_timeout": timedelta(minutes=10),
        "on_failure_callback": notify_failure,
    },
    tags=["legacy", "reconciliation"],
)
def reconciliation():
    @task
    def check_snapshot() -> dict:
        from airflow.sdk import get_current_context

        from reconciliation.lifecycle import begin_run
        from reconciliation.run import check_snapshot as _check

        snapshot = _check()
        begin_run(get_current_context()["run_id"], REPORTS, snapshot)
        LOGGER.info("Snapshot: %s", snapshot)
        return snapshot

    @task
    def reconcile(report: str, snapshot: dict) -> dict:
        from airflow.sdk import get_current_context

        from reconciliation.run import run_report

        result = run_report(report, get_current_context()["run_id"], snapshot)
        LOGGER.info("Kết quả %s: %s", report, result)
        return result

    @task
    def evaluate(results: list[dict]) -> None:
        from airflow.sdk import get_current_context

        from reconciliation.lifecycle import finish_run
        from reconciliation.run import check_snapshot as verify_snapshot

        outcome = finish_run(get_current_context()["run_id"], verify_snapshot())
        LOGGER.info("Reports: %s; run outcome: %s", results, outcome)
        if not outcome["eligible_for_cutover"]:
            raise AirflowFailException(f"Run chưa đủ điều kiện nghiệm thu: {outcome['status']}")

    snapshot = check_snapshot()
    results = reconcile.partial(snapshot=snapshot).expand(report=REPORTS)
    evaluate(results)


reconciliation()

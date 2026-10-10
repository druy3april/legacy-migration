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
        from reconciliation.run import check_snapshot as _check

        snapshot = _check()
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
        by_status: dict[str, list[str]] = {}
        for r in results:
            by_status.setdefault(r["status"], []).append(r["report"])
        LOGGER.info("Tổng hợp đối soát: %s", by_status)
        if "FAIL" in by_status:
            # Không retry: lệch số liệu không tự hết khi chạy lại -> gửi cảnh báo ngay
            raise AirflowFailException(
                f"Đối soát FAIL: {', '.join(by_status['FAIL'])}. "
                "Xem recon.results / recon.row_diffs theo run_id này."
            )
        if set(by_status) == {"SKIP"}:
            LOGGER.warning("Toàn bộ báo cáo SKIP vì snapshot lệch: hôm nay chưa được kiểm chứng")

    snapshot = check_snapshot()
    results = reconcile.partial(snapshot=snapshot).expand(report=REPORTS)
    evaluate(results)


reconciliation()
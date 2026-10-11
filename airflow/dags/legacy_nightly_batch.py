"""Job ban đêm của hệ thống cũ, chạy song song với hệ thống mới trong giai đoạn parallel run.

Chạy ngay sau khi ingest_legacy xong (cùng trạng thái nguồn với raw), ghi snapshot nguồn
vào recon.legacy_batches rồi phát Asset LEGACY_REPORTS.
"""

from datetime import timedelta

import pendulum
from airflow.sdk import dag, task

from common.alerts import notify_failure
from common.assets import LEGACY_REPORTS, WAREHOUSE_RAW


@dag(
    dag_id="legacy_nightly_batch",
    schedule=[WAREHOUSE_RAW],
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
        "execution_timeout": timedelta(minutes=15),
        "on_failure_callback": notify_failure,
    },
    tags=["legacy", "reconciliation"],
)
def legacy_nightly_batch():
    @task(outlets=[LEGACY_REPORTS])
    def run_sp_run_nightly_batch() -> dict:
        from airflow.sdk import get_current_context

        from reconciliation.legacy_batch import run_legacy_batch

        # LegacyBatchUnstable (nguồn đổi trong lúc chạy) -> task lỗi -> retry chạy lại batch
        return run_legacy_batch(batch_id=get_current_context()["run_id"])

    run_sp_run_nightly_batch()


legacy_nightly_batch()

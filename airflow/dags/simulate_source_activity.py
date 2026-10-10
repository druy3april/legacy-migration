"""Giả lập hoạt động kinh doanh hằng ngày ở hệ thống cũ (chỉ dùng trong lab)."""
import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag


@dag(
    dag_id="simulate_source_activity",
    schedule="30 0 * * *",          # 00:30, trước ingest_legacy lúc 01:00
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    tags=["legacy", "lab"],
)
def simulate_source_activity():
    BashOperator(
        task_id="simulate_changes",
        bash_command=(
            "python /opt/airflow/scripts/simulate_changes.py "
            "--update 5 --insert 3 --order-update 20 --order-insert 40 --item-delete 2"
        ),
    )


simulate_source_activity()
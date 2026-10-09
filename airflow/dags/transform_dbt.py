"""Run dbt after ingest_legacy updates the raw schema."""
from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from common.alerts import notify_failure
from common.assets import WAREHOUSE_RAW

DBT = "/home/airflow/dbt-venv/bin/dbt"
DBT_DIR = "/opt/airflow/dbt_project"
DBT_ENV = {
    "DBT_PROFILES_DIR": DBT_DIR,
    "DBT_TARGET_PATH": "/tmp/dbt_target",
    "DBT_LOG_PATH": "/tmp/dbt_logs",
}
DBT_PATH_ARGS = "--target-path /tmp/dbt_target --log-path /tmp/dbt_logs"


@dag(
    dag_id="transform_dbt",
    schedule=[WAREHOUSE_RAW],
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=20),
        "on_failure_callback": notify_failure,
    },
    tags=["legacy", "dbt"],
)
def transform_dbt():
    freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=(
            f"cd {DBT_DIR} && {DBT} source freshness "
            f"--profiles-dir {DBT_DIR} {DBT_PATH_ARGS}"
        ),
        env=DBT_ENV,
        append_env=True,
    )
    build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {DBT_DIR} && {DBT} build --profiles-dir {DBT_DIR} {DBT_PATH_ARGS}",
        env=DBT_ENV,
        append_env=True,
    )
    freshness >> build


transform_dbt()

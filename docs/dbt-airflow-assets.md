# dbt transformation triggered by Airflow Assets

Both DAGs import the same `warehouse_raw` Asset
(`warehouse://postgres/raw`) from `airflow/dags/common/assets.py`. The
`ingest_legacy` DAG publishes it only after all four incremental loads, delete
detection, and the summary task succeed. The `transform_dbt` DAG listens for
that Asset and runs `dbt source freshness` before `dbt build`. A failed
ingestion therefore does not trigger dbt, and dbt can be rerun independently
without rerunning ingestion.

The dbt project is mounted read-only in the Airflow container. The transform
DAG uses writable paths under `/tmp` for dbt logs and compiled artifacts.
Configure the Airflow instance to create scheduled DAGs unpaused; with Docker
Compose this is set by `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=false`.

The same `warehouse_raw` Asset can be consumed later by a reconciliation DAG.

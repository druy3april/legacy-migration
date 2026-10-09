"""Asset shared between raw ingestion and downstream analytics DAGs."""
from airflow.sdk import Asset

WAREHOUSE_RAW = Asset(name="warehouse_raw", uri="warehouse://postgres/raw")

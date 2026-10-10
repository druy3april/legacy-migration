"""Assets dùng chung giữa các DAG: raw -> marts, và báo cáo của hệ thống cũ."""
from airflow.sdk import Asset

WAREHOUSE_RAW = Asset(name="warehouse_raw", uri="warehouse://postgres/raw")
WAREHOUSE_MARTS = Asset(name="warehouse_marts", uri="warehouse://postgres/marts")
LEGACY_REPORTS = Asset(name="legacy_reports", uri="legacy://sqlserver/reports")
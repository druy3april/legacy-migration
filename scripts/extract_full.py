"""Tải toàn bộ một bảng từ SQL Server, ghi thành file Parquet lên MinIO."""
import io
import os
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pymssql
from botocore.exceptions import BotoCoreError, ClientError

from generate_data import get_connection
from init_minio import get_s3_client

TABLE = "customers"
COLUMNS = "customer_id, full_name, email, city, created_at, CAST(row_ver AS BIGINT) AS row_ver"


def extract(conn, table: str, columns: str) -> pa.Table:
    cur = conn.cursor()
    cur.execute(f"SELECT {columns} FROM dbo.{table}")
    names = [col[0] for col in cur.description]
    rows = cur.fetchall()
    data = {name: [row[i] for row in rows] for i, name in enumerate(names)}
    return pa.table(data)


def upload_parquet(s3, bucket: str, key: str, table: pa.Table) -> int:
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    body = buffer.getvalue()
    s3.put_object(Bucket=bucket, Key=key, Body=body)
    return len(body)


def main() -> int:
    try:
        bucket = os.environ["MINIO_BUCKET"]
        s3 = get_s3_client()
        conn = get_connection()
    except KeyError as exc:
        print(f"Thiếu biến môi trường {exc}, hãy kiểm tra file .env")
        return 1
    except pymssql.Error as exc:
        print(f"Không kết nối được SQL Server: {exc}")
        return 1

    with conn:
        table = extract(conn, TABLE, COLUMNS)

    max_ver = max(table["row_ver"].to_pylist()) if table.num_rows else 0
    print(f"Đã đọc {table.num_rows} dòng từ dbo.{TABLE}, row_ver lớn nhất = {max_ver}")

    key = f"raw/{TABLE}/full/{TABLE}.parquet"
    try:
        size = upload_parquet(s3, bucket, key, table)
    except (BotoCoreError, ClientError) as exc:
        print(f"Không ghi được lên MinIO: {exc}")
        return 1
    print(f"Đã ghi s3://{bucket}/{key} ({size} byte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
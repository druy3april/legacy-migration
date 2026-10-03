"""Tải tăng dần một bảng: SQL Server -> Parquet (MinIO) -> Postgres raw, dựa trên watermark rowversion."""
import io
import os
import sys

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import pymssql
from botocore.exceptions import BotoCoreError, ClientError

from generate_data import get_connection
from init_minio import get_s3_client
from load_to_postgres import get_pg_connection

TABLES = {
    "customers": {
        "key": "customer_id",
        "columns": ["customer_id", "full_name", "email", "city", "created_at"],
    },
}


def get_watermark(pg, table: str) -> int:
    with pg.cursor() as cur:
        cur.execute("SELECT last_rowversion FROM etl.watermarks WHERE table_name = %s", (table,))
        row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Chưa có dòng watermark cho bảng {table}, hãy chạy make wh")
    return row[0]


def get_upper_bound(src) -> int:
    cur = src.cursor()
    cur.execute("SELECT CAST(MIN_ACTIVE_ROWVERSION() AS BIGINT) - 1")
    return cur.fetchone()[0]


def extract_to_minio(src, s3, bucket: str, table: str, cfg: dict, last: int, upper: int):
    columns = ", ".join(cfg["columns"] + ["CAST(row_ver AS BIGINT) AS row_ver"])
    cur = src.cursor()
    cur.execute(
        f"SELECT {columns} FROM dbo.{table} "
        "WHERE CAST(row_ver AS BIGINT) > %s AND CAST(row_ver AS BIGINT) <= %s "
        "ORDER BY CAST(row_ver AS BIGINT)",
        (last, upper),
    )
    names = [col[0] for col in cur.description]
    rows = cur.fetchall()
    if not rows:
        return None, 0

    data = {name: [row[i] for row in rows] for i, name in enumerate(names)}
    buffer = io.BytesIO()
    pq.write_table(pa.table(data), buffer)
    key = f"raw/{table}/incremental/rv_{last:020d}_{upper:020d}.parquet"
    s3.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())
    return key, len(rows)


def build_upsert_sql(table: str, key: str, columns: list) -> str:
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{col} = EXCLUDED.{col}" for col in columns if col != key)
    return (
        f"INSERT INTO raw.{table} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({key}) DO UPDATE SET {updates}, _loaded_at = now() "
        f"WHERE EXCLUDED.row_ver > raw.{table}.row_ver"
    )


def load_batch(pg, s3, bucket: str, key, table: str, cfg: dict, upper: int) -> None:
    columns = cfg["columns"] + ["row_ver"]
    with pg.cursor() as cur:
        if key is not None:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            data = pq.read_table(io.BytesIO(body))
            rows = list(zip(*(data[col].to_pylist() for col in columns)))
            cur.executemany(build_upsert_sql(table, cfg["key"], columns), rows)
        cur.execute(
            "UPDATE etl.watermarks SET last_rowversion = %s, last_run_at = now() WHERE table_name = %s",
            (upper, table),
        )


def main() -> int:
    table = sys.argv[1] if len(sys.argv) > 1 else "customers"
    cfg = TABLES.get(table)
    if cfg is None:
        print(f"Chưa cấu hình bảng '{table}'. Các bảng có sẵn: {', '.join(TABLES)}")
        return 1

    try:
        bucket = os.environ["MINIO_BUCKET"]
        s3 = get_s3_client()
        with get_connection() as src, get_pg_connection() as pg:
            last = get_watermark(pg, table)
            upper = get_upper_bound(src)
            print(f"[{table}] watermark cũ = {last}, cận trên an toàn = {upper}")
            if upper <= last:
                print(f"[{table}] Không có gì mới")
                return 0

            key, count = extract_to_minio(src, s3, bucket, table, cfg, last, upper)
            load_batch(pg, s3, bucket, key, table, cfg, upper)
    except KeyError as exc:
        print(f"Thiếu biến môi trường {exc}, hãy kiểm tra file .env")
        return 1
    except (pymssql.Error, psycopg.Error, BotoCoreError, ClientError, RuntimeError) as exc:
        print(f"Lỗi: {exc}")
        return 1

    print(f"[{table}] Đã tải {count} dòng, watermark mới = {upper}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
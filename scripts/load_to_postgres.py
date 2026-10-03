"""Đọc file Parquet trên MinIO và nạp (upsert) vào bảng raw.customers trong Postgres."""
import io
import os
import sys

import psycopg
import pyarrow.parquet as pq
from botocore.exceptions import BotoCoreError, ClientError

from init_minio import get_s3_client

KEY = "raw/customers/full/customers.parquet"
COLUMNS = ["customer_id", "full_name", "email", "city", "created_at", "row_ver"]

UPSERT_SQL = """
INSERT INTO raw.customers (customer_id, full_name, email, city, created_at, row_ver)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (customer_id) DO UPDATE SET
    full_name  = EXCLUDED.full_name,
    email      = EXCLUDED.email,
    city       = EXCLUDED.city,
    created_at = EXCLUDED.created_at,
    row_ver    = EXCLUDED.row_ver,
    _loaded_at = now()
WHERE EXCLUDED.row_ver > raw.customers.row_ver
"""


def get_pg_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
        connect_timeout=10,
    )


def read_parquet(s3, bucket: str, key: str):
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    return pq.read_table(io.BytesIO(body))


def main() -> int:
    try:
        bucket = os.environ["MINIO_BUCKET"]
        s3 = get_s3_client()
        table = read_parquet(s3, bucket, KEY)
    except KeyError as exc:
        print(f"Thiếu biến môi trường {exc}, hãy kiểm tra file .env")
        return 1
    except (BotoCoreError, ClientError) as exc:
        print(f"Không đọc được file từ MinIO: {exc}")
        return 1

    rows = list(zip(*(table[col].to_pylist() for col in COLUMNS)))
    print(f"Đã đọc {len(rows)} dòng từ s3://{bucket}/{KEY}")

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(UPSERT_SQL, rows)
                cur.execute("SELECT COUNT(*), MAX(row_ver) FROM raw.customers")
                total, max_ver = cur.fetchone()
    except KeyError as exc:
        print(f"Thiếu biến môi trường {exc}, hãy kiểm tra file .env")
        return 1
    except psycopg.Error as exc:
        print(f"Lỗi Postgres: {exc}")
        return 1

    print(f"raw.customers hiện có {total} dòng, row_ver lớn nhất = {max_ver}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
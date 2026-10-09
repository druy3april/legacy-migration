"""Tải tăng dần một bảng: SQL Server -> Parquet (MinIO) -> Postgres raw, dựa trên watermark rowversion."""
import io
import os
import sys
import uuid

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
    "products": {
        "key": "product_id",
        "columns": ["product_id", "product_name", "category", "unit_price", "is_active", "created_at"],
    },
    "orders": {
        "key": "order_id",
        "columns": ["order_id", "customer_id", "order_date", "status", "total_amount", "updated_at"],
    },
    "order_items": {
        "key": "order_item_id",
        "columns": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
    },
}


class SchemaDriftError(RuntimeError):
    """Raised when a source table's columns differ from the configured schema."""


def check_schema(src, table: str, cfg: dict) -> None:
    cur = src.cursor()
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = %s",
        (table,),
    )
    source_columns = {row[0] for row in cur.fetchall()}
    expected_columns = set(cfg["columns"]) | {"row_ver"}

    added = sorted(source_columns - expected_columns)
    removed = sorted(expected_columns - source_columns)
    if added or removed:
        changes = []
        if added:
            changes.append(f"cột được thêm: {', '.join(added)}")
        if removed:
            changes.append(f"cột bị thiếu: {', '.join(removed)}")
        raise SchemaDriftError(
            f"Schema nguồn dbo.{table} đã thay đổi ({'; '.join(changes)})"
        )


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


def read_upper_bound() -> int:
    with get_connection() as src:
        return get_upper_bound(src)


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
    updates = [f"{col} = EXCLUDED.{col}" for col in columns if col != key]
    updates.append("_deleted_at = NULL")
    return (
        f"INSERT INTO raw.{table} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({key}) DO UPDATE SET {', '.join(updates)}, _loaded_at = now() "
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


def detect_deletes(table: str) -> int:
    cfg = TABLES.get(table)
    if cfg is None:
        raise ValueError(
            f"Chưa cấu hình bảng '{table}'. Các bảng có sẵn: {', '.join(TABLES)}"
        )

    key = cfg["key"]
    deleted_count = 0
    with get_connection() as src, get_pg_connection() as pg:
        src_cur = src.cursor()
        src_cur.execute(f"SELECT {key} FROM dbo.{table}")

        with pg.cursor() as pg_cur:
            pg_cur.execute("CREATE TEMP TABLE src_keys (k INT PRIMARY KEY) ON COMMIT DROP")
            with pg_cur.copy("COPY src_keys (k) FROM STDIN") as copy:
                while rows := src_cur.fetchmany(10000):
                    for row in rows:
                        copy.write_row((row[0],))

            pg_cur.execute(
                f"UPDATE raw.{table} AS r SET _deleted_at = now() "
                f"WHERE r._deleted_at IS NULL "
                f"AND NOT EXISTS (SELECT 1 FROM src_keys AS s WHERE s.k = r.{key})"
            )
            deleted_count = pg_cur.rowcount

    return deleted_count


def log_ingest(
    pg,
    run_id: str,
    table: str,
    from_rowversion: int,
    to_rowversion: int,
    row_count: int,
    object_key: str | None,
) -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO etl.ingest_log "
            "(run_id, table_name, from_rowversion, to_rowversion, row_count, object_key) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                run_id,
                table,
                from_rowversion,
                to_rowversion,
                row_count,
                object_key,
            ),
        )


def ingest_table(
    table: str, upper: int | None = None, run_id: str = "manual"
) -> dict[str, str | int | None]:
    cfg = TABLES.get(table)
    if cfg is None:
        raise ValueError(
            f"Chưa cấu hình bảng '{table}'. Các bảng có sẵn: {', '.join(TABLES)}"
        )

    with get_connection() as src, get_pg_connection() as pg:
        check_schema(src, table, cfg)
        last = get_watermark(pg, table)
        upper = get_upper_bound(src) if upper is None else upper
        print(f"[{table}] watermark cũ = {last}, cận trên an toàn = {upper}")

        if upper <= last:
            log_ingest(pg, run_id, table, last, last, 0, None)
            return {
                "table": table,
                "rows": 0,
                "from": last,
                "to": last,
                "key": None,
            }

        bucket = os.environ["MINIO_BUCKET"]
        s3 = get_s3_client()
        key, count = extract_to_minio(src, s3, bucket, table, cfg, last, upper)
        load_batch(pg, s3, bucket, key, table, cfg, upper)
        log_ingest(pg, run_id, table, last, upper, count, key)

    return {
        "table": table,
        "rows": count,
        "from": last,
        "to": upper,
        "key": key,
    }


def main() -> int:
    table = sys.argv[1] if len(sys.argv) > 1 else "customers"
    if table == "all":
        tables = list(TABLES)
    elif table in TABLES:
        tables = [table]
    else:
        print(f"Chưa cấu hình bảng '{table}'. Các bảng có sẵn: {', '.join(TABLES)}")
        return 1

    try:
        upper = read_upper_bound()
        run_id = uuid.uuid4().hex
        for selected_table in tables:
            result = ingest_table(selected_table, upper=upper, run_id=run_id)
            print(
                f"[{result['table']}] Đã tải {result['rows']} dòng "
                f"(rowversion {result['from']}..{result['to']})"
            )
    except KeyError as exc:
        print(f"Thiếu biến môi trường {exc}, hãy kiểm tra file .env")
        return 1
    except (
        pymssql.Error,
        psycopg.Error,
        BotoCoreError,
        ClientError,
        RuntimeError,
        ValueError,
        OSError,
    ) as exc:
        print(f"Lỗi: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
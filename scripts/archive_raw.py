"""Archive a complete raw snapshot including tombstones; restore only to restore_* databases."""

import argparse
import hashlib
import io
import json
import os
import re
from pathlib import Path

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import ClientError
from ingest_incremental import TABLES
from init_minio import get_s3_client
from load_to_postgres import get_pg_connection
from psycopg import sql


def digest(body):
    return hashlib.sha256(body).hexdigest()


def put_immutable(s3, bucket, key, body):
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body, IfNoneMatch="*")
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
            raise
        existing = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        if digest(existing) != digest(body):
            raise RuntimeError(f"Object đã tồn tại với nội dung khác: {key}") from exc


def archive(run_id, pg, fingerprint):
    """Caller owns a REPEATABLE READ transaction containing the validated raw state."""
    s3, bucket = get_s3_client(), os.environ["MINIO_BUCKET"]
    manifest = {"version": 1, "run_id": run_id, "fingerprint": fingerprint, "tables": {}}
    for table, cfg in TABLES.items():
        columns = cfg["columns"] + ["row_ver", "_loaded_at", "_deleted_at"]
        with pg.cursor() as cur:
            cur.execute(f"SELECT {', '.join(columns)} FROM raw.{table} ORDER BY {cfg['key']}")
            rows = cur.fetchall()
        data = pa.table({name: [row[i] for row in rows] for i, name in enumerate(columns)})
        buffer = io.BytesIO()
        pq.write_table(data, buffer)
        body = buffer.getvalue()
        checksum = digest(body)
        key = f"raw/{table}/snapshots/{checksum}.parquet"
        put_immutable(s3, bucket, key, body)
        manifest["tables"][table] = {"key": key, "sha256": checksum, "columns": columns, "rows": len(rows)}
    body = json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()
    key = f"manifests/{digest(body)}.json"
    put_immutable(s3, bucket, key, body)
    return key


def validate_manifest(key, body):
    if key != f"manifests/{digest(body)}.json":
        raise ValueError("Manifest key/checksum mismatch")
    manifest = json.loads(body)
    if manifest.get("version") != 1 or set(manifest.get("tables", {})) != set(TABLES):
        raise ValueError("Manifest phải chứa đúng 4 bảng và version=1")
    for table, cfg in TABLES.items():
        item = manifest["tables"][table]
        columns = cfg["columns"] + ["row_ver", "_loaded_at", "_deleted_at"]
        if item["columns"] != columns or item["key"] != f"raw/{table}/snapshots/{item['sha256']}.parquet":
            raise ValueError(f"Manifest schema/key không hợp lệ: {table}")
    return manifest


def restore(key, database):
    if not re.fullmatch(r"restore_[a-z0-9_]{1,40}", database):
        raise ValueError("Database phục hồi phải có tên restore_<chữ thường/số/_>")
    if database == os.environ["POSTGRES_DB"]:
        raise ValueError("Không phục hồi đè database đang dùng")
    s3, bucket = get_s3_client(), os.environ["MINIO_BUCKET"]
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    manifest = validate_manifest(key, body)
    with get_pg_connection() as original:
        params = dict(original.info.get_parameters(), password=os.environ["POSTGRES_PASSWORD"])
    with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
        if not admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone():
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    with psycopg.connect(**dict(params, dbname=database)) as target:
        target.execute((Path(__file__).resolve().parents[1] / "warehouse/raw_restore.sql").read_text())
        target.execute("CREATE TABLE IF NOT EXISTS etl.restore_manifest (key TEXT PRIMARY KEY)")
        previous = target.execute("SELECT key FROM etl.restore_manifest").fetchall()
        if previous:
            if previous != [(key,)]:
                raise RuntimeError("Database này đã chứa snapshot khác; hãy dùng tên restore_ mới")
        else:
            for table in TABLES:
                if target.execute(f"SELECT EXISTS(SELECT 1 FROM raw.{table})").fetchone()[0]:
                    raise RuntimeError("Database đích không rỗng; dừng để giữ dữ liệu")
            for table, item in manifest["tables"].items():
                content = s3.get_object(Bucket=bucket, Key=item["key"])["Body"].read()
                if digest(content) != item["sha256"]:
                    raise RuntimeError(f"Parquet checksum mismatch: {table}")
                data = pq.read_table(io.BytesIO(content))
                if data.column_names != item["columns"] or data.num_rows != item["rows"]:
                    raise RuntimeError(f"Parquet schema/count mismatch: {table}")
                rows = zip(*(data[c].to_pylist() for c in item["columns"]), strict=True)
                with target.cursor() as cur:
                    cur.executemany(
                        f"INSERT INTO raw.{table} ({', '.join(item['columns'])}) "
                        f"VALUES ({', '.join(['%s'] * len(item['columns']))})",
                        rows,
                    )
            target.execute("INSERT INTO etl.restore_manifest VALUES (%s)", (key,))
        # Compare both active data and complete archived rows, including tombstones.
        from reconciliation.fingerprint import fingerprint

        if fingerprint(target) != manifest["fingerprint"]:
            raise RuntimeError("Fingerprint sau phục hồi không khớp")
        for table, item in manifest["tables"].items():
            with target.cursor() as cur:
                cur.execute(f"SELECT {', '.join(item['columns'])} FROM raw.{table} ORDER BY {TABLES[table]['key']}")
                rows = cur.fetchall()
            archived = pq.read_table(io.BytesIO(s3.get_object(Bucket=bucket, Key=item["key"])["Body"].read()))
            expected = list(zip(*(archived[c].to_pylist() for c in item["columns"]), strict=True))
            if rows != expected:
                raise RuntimeError(f"Nội dung phục hồi/tombstone không khớp: {table}")
    print(f"RESTORE PASS: {database}; 4 bảng khớp manifest và tombstone")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    restore(args.manifest, args.database)

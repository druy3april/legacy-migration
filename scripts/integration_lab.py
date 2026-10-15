"""Disposable end-to-end lab; requires the existing local SQL Server/Postgres/MinIO services."""

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pymssql
from dotenv import load_dotenv
from psycopg import sql

load_dotenv()
ROOT = Path(__file__).resolve().parents[1]


def main():
    from init_minio import get_s3_client
    from load_to_postgres import get_pg_connection

    suffix = uuid.uuid4().hex[:10]
    database, source_db = "test_e2e_" + suffix, "GuideTest_" + suffix
    restored, bucket = "restore_e2e_" + suffix, "guide-test-" + suffix
    with get_pg_connection() as original:
        params = dict(original.info.get_parameters(), password=os.environ["POSTGRES_PASSWORD"])
    s3 = get_s3_client()
    sql_params = dict(
        server=os.getenv("MSSQL_HOST", "localhost"),
        port=int(os.getenv("MSSQL_PORT", "1433")),
        user="sa",
        password=os.environ["MSSQL_SA_PASSWORD"],
        database="master",
    )
    env = dict(
        os.environ,
        POSTGRES_DB=database,
        MSSQL_DATABASE=source_db,
        MINIO_BUCKET=bucket,
        MAX_DELETE_RATIO="0.10",
        PYTHONPATH=str(ROOT / "scripts") + ":" + str(ROOT),
        DBT_PROJECT_DIR=str(ROOT / "dbt_project"),
        DBT_SEND_ANONYMOUS_USAGE_STATS="false",
    )
    created_pg, created_source, created_bucket = False, False, False

    def run(*args, expected=0):
        print("\nSTEP:", " ".join(args), flush=True)
        result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env)
        if result.returncode != expected:
            raise RuntimeError(f"{args}: exit {result.returncode}, expected {expected}")

    def load_pg(path):
        # psql is available inside the already-running postgres container.
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                params["user"],
                "-d",
                database,
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input=(ROOT / path).read_text(),
            text=True,
            cwd=ROOT,
            env=os.environ,
            check=True,
        )

    with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
        source_admin = pymssql.connect(**sql_params, autocommit=True)
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            created_pg = True
            source_admin.cursor().execute(f"CREATE DATABASE [{source_db}]")
            created_source = True
            s3.create_bucket(Bucket=bucket)
            created_bucket = True
            load_pg("warehouse/init.sql")
            load_pg("warehouse/init.sql")  # migration must be rerunnable
            load_pg("ci/sample_raw_data.sql")
            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
                for path in ["sql/01_schema.sql", "sql/02_stored_procedures.sql"]:
                    content = (ROOT / path).read_text().replace("USE LegacyRetail", f"USE [{source_db}]")
                    for batch in re.split(r"^\s*GO\s*$", content, flags=re.MULTILINE | re.IGNORECASE):
                        if batch.strip():
                            source.cursor().execute(batch)
                            source.commit()
                source.cursor().execute("CREATE USER bi_legacy_reader WITHOUT LOGIN")
                source.commit()
                from ingest_incremental import TABLES

                with psycopg.connect(**dict(params, dbname=database)) as pg:
                    for table, cfg in TABLES.items():
                        columns = ", ".join(cfg["columns"])
                        rows = pg.execute(f"SELECT {columns} FROM raw.{table} WHERE _deleted_at IS NULL").fetchall()
                        cur = source.cursor()
                        cur.execute(f"SET IDENTITY_INSERT dbo.{table} ON")
                        cur.executemany(
                            f"INSERT INTO dbo.{table} ({columns}) VALUES ({', '.join(['%s'] * len(cfg['columns']))})",
                            rows,
                        )
                        cur.execute(f"SET IDENTITY_INSERT dbo.{table} OFF")
                        source.commit()
                    pg.execute("TRUNCATE raw.customers,raw.products,raw.orders,raw.order_items,etl.ingest_log")
                    pg.execute("UPDATE etl.watermarks SET last_rowversion=0,last_run_at=NULL")
            run("scripts/ingest_incremental.py", "all")
            run("scripts/ingest_incremental.py", "all")  # retry: no duplicate keys, zero deltas
            with psycopg.connect(**dict(params, dbname=database)) as pg:
                latest = pg.execute(
                    "SELECT run_id FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1"
                ).fetchone()[0]
                assert (
                    pg.execute("SELECT sum(row_count) FROM etl.ingest_log WHERE run_id=%s", (latest,)).fetchone()[0]
                    == 0
                )
            run("-m", "reconciliation.legacy_batch")
            run("-m", "reconciliation.build")
            run("-m", "reconciliation.run")
            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
                cur = source.cursor()
                cur.execute("EXECUTE AS USER = 'bi_legacy_reader'")
                try:
                    cur.execute("SELECT COUNT(*) FROM dbo.category_monthly_revenue")
                    assert cur.fetchone()[0] == 3
                    cur.execute("SELECT HAS_PERMS_BY_NAME('dbo.orders', 'OBJECT', 'SELECT')")
                    assert cur.fetchone()[0] == 0
                finally:
                    cur.execute("REVERT")
            with psycopg.connect(**dict(params, dbname=database)) as pg:
                assert pg.execute(
                    "SELECT eligible_for_cutover FROM recon.runs ORDER BY finished_at DESC LIMIT 1"
                ).fetchone()[0]
                count = pg.execute("SELECT count(*) FROM recon.results").fetchone()[0]
            run("-m", "reconciliation.run", "--ignore-snapshot", expected=2)
            with psycopg.connect(**dict(params, dbname=database)) as pg:
                assert pg.execute("SELECT count(*) FROM recon.results").fetchone()[0] == count
            # Change a value at source: snapshot must refuse certification and CLI must fail.
            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
                source.cursor().execute("UPDATE dbo.customers SET city=N'Hà Nội 2' WHERE customer_id=1")
                source.commit()
            run("-m", "reconciliation.run", expected=1)
            # Hard delete one of 17 items; 10% is scoped ONLY to this disposable small fixture.
            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
                source.cursor().execute("DELETE FROM dbo.order_items WHERE order_item_id=17")
                source.cursor().execute("UPDATE dbo.orders SET total_amount=0 WHERE order_id=12")
                source.commit()
            run("scripts/ingest_incremental.py", "all")
            run("-m", "reconciliation.legacy_batch")
            run("-m", "reconciliation.build")
            run("-m", "reconciliation.run")
            with psycopg.connect(**dict(params, dbname=database)) as pg:
                assert pg.execute(
                    "SELECT _deleted_at IS NOT NULL FROM raw.order_items WHERE order_item_id=17"
                ).fetchone()[0]
                manifest = pg.execute(
                    "SELECT manifest_key FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1"
                ).fetchone()[0]
            run("scripts/archive_raw.py", manifest, "--database", restored)
            run("scripts/archive_raw.py", manifest, "--database", restored)  # replay is idempotent
            # A later partial build must not inherit an older full PASS.
            run("-m", "reconciliation.build", "--select", "mart_daily_revenue", expected=2)
            run("-m", "reconciliation.run", expected=1)
            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
                cur = source.cursor()
                cur.execute(
                    "DELETE FROM dbo.order_items; DELETE FROM dbo.orders; EXEC dbo.sp_refresh_category_monthly_revenue"
                )
                source.commit()
                cur.execute("SELECT * FROM dbo.category_monthly_revenue")
                assert cur.fetchall() == []
                assert [column[0] for column in cur.description] == ["category"]
                cur.execute("EXECUTE AS USER = 'bi_legacy_reader'")
                try:
                    cur.execute("SELECT COUNT(*) FROM dbo.category_monthly_revenue")
                    assert cur.fetchone()[0] == 0
                finally:
                    cur.execute("REVERT")
            print(
                "E2E PASS: retry, reconciliation, debug, stale snapshot, delete, "
                "restore twice, partial build, pivot BI grants",
                flush=True,
            )
        finally:
            if created_pg:
                for name in [database, restored]:
                    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
            if created_source:
                cur = source_admin.cursor()
                cur.execute(f"ALTER DATABASE [{source_db}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
                cur.execute(f"DROP DATABASE [{source_db}]")
            source_admin.close()
            if created_bucket:
                for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                    objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
                    if objects:
                        s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
                s3.delete_bucket(Bucket=bucket)


if __name__ == "__main__":
    main()

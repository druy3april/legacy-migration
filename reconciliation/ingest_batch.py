"""Publish a completed ingestion only after source and raw contents match."""

from archive_raw import archive
from psycopg import IsolationLevel
from psycopg.types.json import Jsonb

from reconciliation.db import get_legacy_connection, get_pg_connection
from reconciliation.fingerprint import fingerprint


def complete_ingestion(run_id):
    with get_legacy_connection() as source, get_pg_connection() as pg:
        pg.isolation_level = IsolationLevel.REPEATABLE_READ
        pg.execute("SELECT pg_advisory_xact_lock(73001)")
        before = fingerprint(source, source=True)
        current = fingerprint(pg)
        if before != current:
            raise RuntimeError("Nguồn và raw chưa cùng trạng thái; chạy lại ingestion đầy đủ")
        with pg.cursor() as cur:
            cur.execute("SELECT table_name FROM etl.ingest_log WHERE run_id=%s", (run_id,))
            if {r[0] for r in cur.fetchall()} != set(current):
                raise RuntimeError("Ingestion chưa có log đủ 4 bảng")
        manifest_key = archive(run_id, pg, current)
        after = fingerprint(source, source=True)
        if before != after:
            raise RuntimeError("Nguồn thay đổi khi chốt batch; chưa phát hành batch này")
        pg.execute(
            "INSERT INTO etl.ingest_batches(run_id, fingerprint, manifest_key) VALUES (%s,%s,%s) "
            "ON CONFLICT(run_id) DO UPDATE SET fingerprint=EXCLUDED.fingerprint, "
            "manifest_key=EXCLUDED.manifest_key, finished_at=now()",
            (run_id, Jsonb(current), manifest_key),
        )
    return manifest_key


def latest_ingestion(pg):
    row = pg.execute(
        "SELECT run_id,fingerprint,finished_at FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise RuntimeError("Chưa có batch ingestion hoàn tất: chạy make ingest-all hoặc DAG ingest_legacy")
    return {"run_id": row[0], "fingerprint": row[1], "finished_at": row[2]}

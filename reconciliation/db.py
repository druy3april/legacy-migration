"""Đọc dữ liệu hai phía, lấy dấu vân tay snapshot và ghi kết quả vào schema recon."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from generate_data import (
    get_connection as get_legacy_connection,  # noqa: F401  (pymssql)
)
from load_to_postgres import get_pg_connection  # noqa: F401  (psycopg)
from psycopg.types.json import Jsonb

from reconciliation.compare import CheckResult, Dataset, RowDiff

SOURCE_TABLES = ("customers", "products", "orders", "order_items")
MAX_ROW_DIFFS = 200  # mỗi báo cáo chỉ lưu tối đa chừng này dòng lệch để xem chi tiết


def fetch_dataset(conn, table: str, columns: list[str] | None = None) -> Dataset:
    """Câu SELECT trung tính, chạy được trên cả SQL Server lẫn Postgres."""
    cur = conn.cursor()
    try:
        select_list = "*" if columns is None else ", ".join(columns)
        cur.execute(f"SELECT {select_list} FROM {table}")
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
    finally:
        cur.close()
    return Dataset(columns=names, rows=rows)


# ---------------------------------------------------------------- snapshot


def legacy_fingerprint(mssql):
    from reconciliation.fingerprint import fingerprint

    return fingerprint(mssql, source=True)


def raw_fingerprint(pg):
    from reconciliation.fingerprint import fingerprint

    return fingerprint(pg)


def record_legacy_batch(
    pg,
    batch_id: str,
    started_at: datetime,
    finished_at: datetime,
    before: dict,
    after: dict,
    ingest_run_id: str | None = None,
) -> bool:
    stable = before == after
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO recon.legacy_batches "
            "(batch_id, started_at, finished_at, fingerprint_before, fingerprint_after, stable, ingest_run_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (batch_id) DO UPDATE SET started_at = EXCLUDED.started_at, "
            "finished_at = EXCLUDED.finished_at, fingerprint_before = EXCLUDED.fingerprint_before, "
            "fingerprint_after = EXCLUDED.fingerprint_after, stable = EXCLUDED.stable, "
            "ingest_run_id=EXCLUDED.ingest_run_id",
            (batch_id, started_at, finished_at, Jsonb(before), Jsonb(after), stable, ingest_run_id),
        )
    return stable


def latest_legacy_batch(pg) -> dict | None:
    with pg.cursor() as cur:
        cur.execute(
            "SELECT batch_id, finished_at, fingerprint_after, stable, ingest_run_id "
            "FROM recon.legacy_batches ORDER BY finished_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {"batch_id": row[0], "finished_at": row[1], "fingerprint": row[2], "stable": row[3], "ingest_run_id": row[4]}


# ---------------------------------------------------------------- ghi kết quả


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def write_outcome(
    pg, run_id: str, report: str, batch_id: str | None, results: list[CheckResult], diffs: list[RowDiff]
) -> None:
    """Xóa kết quả cũ của (run_id, report) rồi ghi lại, để chạy lại task không nhân đôi."""
    with pg.cursor() as cur:
        cur.execute("DELETE FROM recon.results WHERE run_id = %s AND report = %s", (run_id, report))
        cur.execute("DELETE FROM recon.row_diffs WHERE run_id = %s AND report = %s", (run_id, report))
        cur.executemany(
            "INSERT INTO recon.results (run_id, legacy_batch_id, report, check_level, check_name, "
            "legacy_value, new_value, diff_count, tolerance, status, details) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    run_id,
                    batch_id,
                    r.report,
                    r.level,
                    r.name,
                    r.legacy_value,
                    r.new_value,
                    r.diff_count,
                    r.tolerance,
                    r.status,
                    Jsonb(_json_safe(r.details)) if r.details else None,
                )
                for r in results
            ],
        )
        if diffs:
            cur.executemany(
                "INSERT INTO recon.row_diffs (run_id, report, key, diff_type, column_name, "
                "legacy_value, new_value) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        run_id,
                        d.report,
                        Jsonb(_json_safe(d.key)),
                        d.diff_type,
                        d.column,
                        None if d.legacy_value is None else str(d.legacy_value),
                        None if d.new_value is None else str(d.new_value),
                    )
                    for d in diffs[:MAX_ROW_DIFFS]
                ],
            )

"""Chạy job ban đêm của hệ thống cũ và ghi lại snapshot nguồn mà job đã dùng.

    python -m reconciliation.legacy_batch [batch_id]
"""
import sys
import uuid
from datetime import datetime, timezone

from reconciliation.db import (
    get_legacy_connection,
    get_pg_connection,
    legacy_fingerprint,
    record_legacy_batch,
)


class LegacyBatchUnstable(RuntimeError):
    """Nguồn thay đổi trong lúc batch chạy: báo cáo cũ không ứng với một snapshot rõ ràng."""


def run_legacy_batch(batch_id: str) -> dict:
    with get_legacy_connection() as mssql:
        before = legacy_fingerprint(mssql)
        started_at = datetime.now(timezone.utc)
        cur = mssql.cursor()
        cur.execute("EXEC dbo.sp_run_nightly_batch")
        mssql.commit()
        finished_at = datetime.now(timezone.utc)
        after = legacy_fingerprint(mssql)

    with get_pg_connection() as pg:
        stable = record_legacy_batch(pg, batch_id, started_at, finished_at, before, after)

    if not stable:
        raise LegacyBatchUnstable(
            f"Nguồn thay đổi trong lúc chạy batch {batch_id}: trước={before}, sau={after}"
        )
    return {"batch_id": batch_id, "seconds": (finished_at - started_at).total_seconds(),
            "fingerprint": after}


def main() -> int:
    batch_id = sys.argv[1] if len(sys.argv) > 1 else f"manual__{uuid.uuid4().hex[:12]}"
    try:
        result = run_legacy_batch(batch_id)
    except LegacyBatchUnstable as exc:
        print(f"CẢNH BÁO: {exc}")
        return 1
    print(f"Batch {result['batch_id']} xong sau {result['seconds']:.1f}s, snapshot={result['fingerprint']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
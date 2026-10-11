"""Đối soát báo cáo cũ (SQL Server) với mart dbt (Postgres).

python -m reconciliation.run                 # tất cả báo cáo
python -m reconciliation.run daily_revenue   # một báo cáo
python -m reconciliation.run --ignore-snapshot   # so dù snapshot lệch (chỉ để debug)
"""

import argparse
import os
import sys
import uuid
from decimal import Decimal

from reconciliation.compare import (
    FAIL,
    SKIP,
    CheckResult,
    ReportOutcome,
    reconcile,
)
from reconciliation.db import (
    fetch_dataset,
    get_legacy_connection,
    get_pg_connection,
    latest_legacy_batch,
    raw_fingerprint,
    write_outcome,
)
from reconciliation.specs import REPORTS

TOLERANCE = Decimal(os.getenv("RECON_MONEY_TOLERANCE", "0.01"))


def check_snapshot() -> dict:
    """Báo cáo cũ và mart mới phải được tính từ CÙNG một trạng thái nguồn.

    So dấu vân tay (số dòng + rowversion lớn nhất của 4 bảng) lúc batch cũ chạy
    với dấu vân tay của raw Postgres (dữ liệu mà dbt vừa dùng).
    """
    with get_pg_connection() as pg:
        batch = latest_legacy_batch(pg)
        current = raw_fingerprint(pg)
    if batch is None:
        return {"ok": False, "batch_id": None, "reason": "Chưa có batch cũ nào được ghi nhận (chạy make legacy-batch)"}
    if not batch["stable"]:
        return {"ok": False, "batch_id": batch["batch_id"], "reason": "Batch cũ gần nhất chạy khi nguồn đang thay đổi"}
    mismatched = {
        t: {"legacy_batch": batch["fingerprint"].get(t), "raw": fp}
        for t, fp in current.items()
        if batch["fingerprint"].get(t) != fp
    }
    if mismatched:
        return {
            "ok": False,
            "batch_id": batch["batch_id"],
            "reason": "Snapshot lệch giữa batch cũ và raw",
            "tables": mismatched,
        }
    return {"ok": True, "batch_id": batch["batch_id"], "reason": "Snapshot khớp"}


def run_report(name: str, run_id: str, snapshot: dict, ignore_snapshot: bool = False) -> dict:
    spec = REPORTS[name]
    batch_id = snapshot.get("batch_id")

    if not snapshot["ok"] and not ignore_snapshot:
        outcome = ReportOutcome(
            name,
            [
                CheckResult(
                    name,
                    "L0_snapshot",
                    "cùng thời điểm cắt",
                    SKIP,
                    details={k: v for k, v in snapshot.items() if k != "ok"},
                )
            ],
        )
    else:
        try:
            columns = None if spec.pivot_id else spec.column_names
            with get_legacy_connection() as mssql:
                legacy = fetch_dataset(mssql, spec.legacy_table, columns)
            with get_pg_connection() as pg:
                new = fetch_dataset(pg, spec.new_table, columns)
            outcome = reconcile(spec, legacy, new, TOLERANCE)
        except Exception as exc:  # lỗi đọc bảng cũng là kết quả đối soát FAIL
            outcome = ReportOutcome(
                name,
                [
                    CheckResult(
                        name,
                        "L0_error",
                        type(exc).__name__,
                        FAIL,
                        details={"error": str(exc)[:1000]},
                    )
                ],
            )

    with get_pg_connection() as pg:
        write_outcome(pg, run_id, name, batch_id, outcome.results, outcome.diffs)

    return {
        "report": name,
        "status": outcome.status,
        "failed_checks": [f"{r.level}:{r.name}" for r in outcome.results if r.status == FAIL],
        "diff_rows": sum(r.diff_count for r in outcome.results if r.level == "L4_row"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reports", nargs="*", help=f"bỏ trống = tất cả: {', '.join(REPORTS)}")
    parser.add_argument("--run-id", default=f"manual__{uuid.uuid4().hex[:12]}")
    parser.add_argument("--ignore-snapshot", action="store_true")
    args = parser.parse_args()
    unknown = [r for r in args.reports if r not in REPORTS]
    if unknown:
        parser.error(f"Báo cáo không tồn tại: {', '.join(unknown)}")

    snapshot = check_snapshot()
    print(f"Snapshot: {snapshot['reason']} (batch={snapshot.get('batch_id')})")
    if not snapshot["ok"] and "tables" in snapshot:
        for table, sides in snapshot["tables"].items():
            print(f"  {table}: batch cũ={sides['legacy_batch']} raw={sides['raw']}")

    summaries = [
        run_report(name, args.run_id, snapshot, args.ignore_snapshot) for name in (args.reports or list(REPORTS))
    ]

    print(f"\nrun_id = {args.run_id}")
    print(f"{'Báo cáo':<28}{'Trạng thái':<12}{'Dòng lệch':>10}  Kiểm tra lỗi")
    for s in summaries:
        print(f"{s['report']:<28}{s['status']:<12}{s['diff_rows']:>10}  {', '.join(s['failed_checks'])}")
    return 1 if any(s["status"] == FAIL for s in summaries) else 0


if __name__ == "__main__":
    sys.exit(main())

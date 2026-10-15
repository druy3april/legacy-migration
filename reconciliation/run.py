"""Đối soát báo cáo cũ (SQL Server) với mart dbt (Postgres).

python -m reconciliation.run                 # tất cả báo cáo
python -m reconciliation.run daily_revenue   # một báo cáo
python -m reconciliation.run --ignore-snapshot   # so dù snapshot lệch (chỉ để debug)
"""

import argparse
import os
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from reconciliation.compare import (
    FAIL,
    PASS,
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
    from reconciliation.db import legacy_fingerprint
    from reconciliation.ingest_batch import latest_ingestion

    with get_pg_connection() as pg:
        try:
            ingest = latest_ingestion(pg)
        except RuntimeError as exc:
            return {"ok": False, "reason": str(exc)}
        batch = latest_legacy_batch(pg)
        current = raw_fingerprint(pg)
        build = pg.execute(
            "SELECT build_id,ingest_run_id,fingerprint,status,invocation_id "
            "FROM etl.dbt_builds ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    result = {
        "ok": False,
        "reason": "Chưa đủ batch cũ và build dbt đã ghi nhận",
        "ingest_run_id": ingest["run_id"],
        "batch_id": batch["batch_id"] if batch else None,
        "build_id": build[0] if build else None,
    }
    if not batch or not build:
        return result
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    if ingest["finished_at"].astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date() != today:
        result["reason"] = "Chưa có ingestion hoàn tất trong ngày hôm nay"
        return result
    with get_legacy_connection() as mssql:
        source = legacy_fingerprint(mssql)
    matches = (
        batch["stable"]
        and build[3] == "PASS"
        and batch["ingest_run_id"] == build[1] == ingest["run_id"]
        and batch["fingerprint"] == build[2] == ingest["fingerprint"] == current == source
    )
    result.update(ok=bool(matches), reason="Snapshot khớp" if matches else "Snapshot hoặc batch ID không khớp")
    result["fingerprint"] = current
    result["dbt_invocation_id"] = build[4]
    return result


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
            outcome.results.insert(
                0,
                CheckResult(
                    name,
                    "L0_snapshot",
                    "cùng batch dữ liệu",
                    PASS if snapshot["ok"] else SKIP,
                    details={k: v for k, v in snapshot.items() if k != "fingerprint"},
                ),
            )
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

    if not ignore_snapshot:
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

    from reconciliation.lifecycle import begin_run, finish_run

    reports = args.reports or list(REPORTS)
    if not args.ignore_snapshot:
        begin_run(args.run_id, reports, snapshot)
    summaries = [run_report(name, args.run_id, snapshot, args.ignore_snapshot) for name in reports]

    print(f"\nrun_id = {args.run_id}")
    print(f"{'Báo cáo':<28}{'Trạng thái':<12}{'Dòng lệch':>10}  Kiểm tra lỗi")
    for s in summaries:
        print(f"{s['report']:<28}{s['status']:<12}{s['diff_rows']:>10}  {', '.join(s['failed_checks'])}")
    if args.ignore_snapshot:
        print("DEBUG: không ghi kết quả, không đủ điều kiện cutover")
        return 2
    outcome = finish_run(args.run_id, check_snapshot())
    print("Run:", outcome)
    return 0 if outcome["status"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())

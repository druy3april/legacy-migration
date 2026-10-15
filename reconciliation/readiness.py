"""Kiểm tra điều kiện cutover: đủ N ngày đối soát xanh liên tiếp (docs/cutover_plan.md).

python -m reconciliation.readiness            # N lấy từ CUTOVER_GREEN_DAYS, mặc định 5
python -m reconciliation.readiness --days 7

Trả về exit code 0 khi đủ điều kiện, 1 khi chưa đủ. Định nghĩa ngày xanh nằm trong
view recon.v_daily_summary (warehouse/init.sql).
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
HISTORY_DAYS = 10


def evaluate(green_days: int, last_run_date: date | None, today: date, required: int) -> list[str]:
    """Trả về danh sách lý do chưa đạt; rỗng = đạt. Tách riêng để unit test không cần database.

    green_days là chuỗi xanh kết thúc ở last_run_date (ngày chạy gần nhất không xanh => 0).
    """
    if required < 1:
        raise ValueError("Số ngày yêu cầu phải >= 1")
    if last_run_date is not None and last_run_date > today:
        return ["Ngày đối soát nằm trong tương lai: kiểm tra đồng hồ hệ thống"]
    if last_run_date is None:
        return ["chưa có lần đối soát nào trong recon.results"]
    problems = []
    if green_days == 0:
        problems.append(f"ngày chạy gần nhất ({last_run_date}) chưa xanh")
    elif green_days < required:
        problems.append(f"mới có {green_days}/{required} ngày xanh liên tiếp")
    if last_run_date < today - timedelta(days=1):
        problems.append(f"lần đối soát gần nhất là {last_run_date}, cũ hơn hôm qua: pipeline có thể đã ngừng chạy")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=None, help="số ngày xanh liên tiếp cần có")
    args = parser.parse_args()

    # Import ở đây để unit test evaluate() không cần driver database
    from reconciliation.db import get_pg_connection

    required = args.days if args.days is not None else int(os.getenv("CUTOVER_GREEN_DAYS", "5"))

    with get_pg_connection() as pg, pg.cursor() as cur:
        cur.execute("SELECT green_days, since, until, last_run_date FROM recon.v_green_streak")
        green_days, since, until, last_run_date = cur.fetchone()
        cur.execute(
            "SELECT run_date, reports, pass_count, warn_count, skip_count, fail_count, diff_rows, green "
            "FROM recon.v_daily_summary ORDER BY run_date DESC LIMIT %s",
            (HISTORY_DAYS,),
        )
        history = cur.fetchall()

    today = datetime.now(LOCAL_TZ).date()
    print(f"{'Ngày':<12}{'Báo cáo':>8}{'PASS':>6}{'WARN':>6}{'SKIP':>6}{'FAIL':>6}{'Lệch':>7}  Xanh")
    for run_date, reports, ok, warn, skip, fail, diff_rows, green in history:
        flag = "có" if green else "không"
        print(f"{run_date!s:<12}{reports:>8}{ok:>6}{warn:>6}{skip:>6}{fail:>6}{diff_rows:>7}  {flag}")

    streak = f"{green_days} ngày (từ {since} đến {until})" if green_days else "0 ngày"
    print(f"\nChuỗi xanh: {streak}; ngày chạy gần nhất: {last_run_date}")
    problems = evaluate(green_days, last_run_date, today, required)
    if problems:
        print("CHƯA ĐỦ điều kiện cutover: " + "; ".join(problems))
        return 1
    print(f"ĐỦ điều kiện cutover: {green_days} ngày xanh liên tiếp (yêu cầu {required}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

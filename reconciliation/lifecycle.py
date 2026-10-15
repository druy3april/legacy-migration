"""A run is certified only after all seven reports and their checks complete."""

from collections import Counter, defaultdict

from psycopg.types.json import Jsonb

from reconciliation.db import get_pg_connection
from reconciliation.specs import REPORTS


def expected_levels(spec):
    aggregates = sum(
        2 if col.kind == "text" else 3 if col.kind == "date" else 4
        for col in spec.value_columns
        if col.name not in spec.tie_columns
    )
    return Counter(
        {
            "L0_snapshot": 1,
            "L1_row_count": 2 if spec.pivot_id else 1,
            "L2_aggregate": aggregates,
            "L3_group": 1,
            "L4_row": 1,
            "L5_checksum": 1,
        }
    )


def begin_run(run_id, reports, snapshot):
    with get_pg_connection() as pg, pg.cursor() as cur:
        cur.execute("DELETE FROM recon.results WHERE run_id=%s", (run_id,))
        cur.execute("DELETE FROM recon.row_diffs WHERE run_id=%s", (run_id,))
        cur.execute(
            "INSERT INTO recon.runs(run_id, requested_reports, snapshot, status) VALUES (%s,%s,%s,'RUNNING') "
            "ON CONFLICT(run_id) DO UPDATE SET requested_reports=EXCLUDED.requested_reports, "
            "snapshot=EXCLUDED.snapshot, started_at=now(), finished_at=NULL, "
            "status='RUNNING', eligible_for_cutover=false",
            (run_id, reports, Jsonb(snapshot)),
        )


def classify_checks(rows, reports, snapshot_ok):
    by_report = defaultdict(list)
    for report, level, status in rows:
        by_report[report].append((level, status))
    complete = set(by_report) == set(reports)
    for report in reports:
        complete &= Counter(level for level, _ in by_report[report]) == expected_levels(REPORTS[report])
    statuses = {status for _, _, status in rows}
    if "FAIL" in statuses:
        status = "FAIL"
    elif "SKIP" in statuses or not snapshot_ok:
        status = "SKIP"
    elif not complete:
        status = "INCOMPLETE"
    elif "WARN" in statuses:
        status = "WARN"
    else:
        status = "PASS"
    eligible = complete and snapshot_ok and status == "PASS" and set(reports) == set(REPORTS)
    return status, eligible


def finish_run(run_id, snapshot_after):
    with get_pg_connection() as pg, pg.cursor() as cur:
        cur.execute("SELECT requested_reports,snapshot FROM recon.runs WHERE run_id=%s FOR UPDATE", (run_id,))
        record = cur.fetchone()
        if record is None:
            raise RuntimeError("Run chưa được khởi tạo")
        reports, snapshot_before = record
        cur.execute("SELECT report,check_level,status FROM recon.results WHERE run_id=%s", (run_id,))
        snapshot_ok = bool(snapshot_before.get("ok")) and snapshot_before == snapshot_after
        status, eligible = classify_checks(cur.fetchall(), reports, snapshot_ok)
        cur.execute(
            "UPDATE recon.runs SET finished_at=now(),status=%s,eligible_for_cutover=%s WHERE run_id=%s",
            (status, eligible, run_id),
        )
    return {"status": status, "eligible_for_cutover": eligible}

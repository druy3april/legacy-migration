"""SQL integration tests; enabled only for a disposable test_* database."""

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from load_to_postgres import get_pg_connection

from reconciliation.specs import REPORTS


@unittest.skipUnless(os.getenv("MIGRATION_TEST_DB"), "requires disposable test database")
class WarehouseGuardTests(unittest.TestCase):
    def setUp(self):
        database = os.environ["MIGRATION_TEST_DB"]
        if not database.startswith("test_") or database != os.environ.get("POSTGRES_DB"):
            raise RuntimeError("Integration tests require POSTGRES_DB=MIGRATION_TEST_DB=test_...")
        self.pg = get_pg_connection()
        self.pg.execute("DELETE FROM recon.runs")
        self.pg.execute("DELETE FROM recon.results")

    def tearDown(self):
        self.pg.rollback()
        self.pg.close()

    def add_run(self, run_id, day, reports=None, eligible=True):
        reports = list(REPORTS) if reports is None else reports
        timestamp = f"{day} 01:00:00+07"
        self.pg.execute(
            "INSERT INTO recon.runs(run_id,requested_reports,snapshot,started_at,"
            "finished_at,status,eligible_for_cutover) "
            "VALUES (%s,%s,'{}',%s,%s,'PASS',%s)",
            (run_id, reports, timestamp, timestamp, eligible),
        )
        for report in reports:
            self.pg.execute(
                "INSERT INTO recon.results(run_id,report,check_level,check_name,status,checked_at) "
                "VALUES (%s,%s,'L1_row_count','test','PASS',%s)",
                (run_id, report, timestamp),
            )

    def test_partial_runs_are_not_combined(self):
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        reports = list(REPORTS)
        self.add_run("partial-a", today, reports[:4], False)
        self.add_run("partial-b", today, reports[4:], False)
        self.assertEqual(self.pg.execute("SELECT count(*) FROM recon.v_daily_summary WHERE green").fetchone()[0], 0)

    def test_calendar_gap_breaks_streak(self):
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        for days in [0, 1, 3, 4, 5]:
            self.add_run(f"run-{days}", today - timedelta(days=days))
        self.assertEqual(self.pg.execute("SELECT green_days FROM recon.v_green_streak").fetchone()[0], 2)

    def test_stale_streak_counts_as_zero(self):
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        for days in range(3, 8):
            self.add_run(f"run-{days}", today - timedelta(days=days))
        self.assertEqual(self.pg.execute("SELECT green_days FROM recon.v_green_streak").fetchone()[0], 0)

    def test_each_table_has_independent_freshness(self):
        self.pg.execute("UPDATE etl.ingest_log SET loaded_at=now()-interval '10 days' WHERE table_name<>'customers'")
        row = self.pg.execute(
            "SELECT (SELECT loaded_at>now()-interval '1 day' FROM etl.freshness_customers),"
            "(SELECT loaded_at<now()-interval '9 days' FROM etl.freshness_orders)"
        ).fetchone()
        self.assertEqual(row, (True, True))

    def test_missing_ingest_log_is_stale(self):
        self.pg.execute("DELETE FROM etl.ingest_log WHERE table_name='products'")
        self.assertTrue(
            self.pg.execute("SELECT loaded_at<now()-interval '50 hours' FROM etl.freshness_products").fetchone()[0]
        )

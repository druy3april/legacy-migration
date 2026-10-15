import contextlib
import io
import sys
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from archive_raw import digest, validate_manifest
from schema_contract import CONTRACT, schema_differences

from reconciliation import run
from reconciliation.compare import Dataset, reconcile
from reconciliation.lifecycle import classify_checks, expected_levels
from reconciliation.readiness import evaluate
from reconciliation.specs import REPORTS


def full_checks():
    return [
        (name, level, "PASS")
        for name, spec in REPORTS.items()
        for level, count in expected_levels(spec).items()
        for _ in range(count)
    ]


class OperationalGuardTests(unittest.TestCase):
    def test_complete_run_is_eligible(self):
        self.assertEqual(classify_checks(full_checks(), list(REPORTS), True), ("PASS", True))

    def test_missing_report_is_incomplete(self):
        rows = [r for r in full_checks() if r[0] != "customer_ltv"]
        self.assertEqual(classify_checks(rows, list(REPORTS), True), ("INCOMPLETE", False))

    def test_missing_check_is_incomplete(self):
        self.assertEqual(classify_checks(full_checks()[1:], list(REPORTS), True), ("INCOMPLETE", False))

    def test_changed_snapshot_is_not_eligible(self):
        self.assertEqual(classify_checks(full_checks(), list(REPORTS), False), ("SKIP", False))

    def test_partial_report_set_never_qualifies(self):
        rows = [r for r in full_checks() if r[0] == "daily_revenue"]
        self.assertEqual(classify_checks(rows, ["daily_revenue"], True), ("PASS", False))

    def test_warn_never_qualifies(self):
        rows = full_checks()
        rows[0] = (*rows[0][:2], "WARN")
        self.assertEqual(classify_checks(rows, list(REPORTS), True), ("WARN", False))

    def test_expected_levels_match_actual_engine_for_each_report(self):
        for name, spec in REPORTS.items():
            columns = [spec.pivot_id, "2026-10"] if spec.pivot_id else spec.column_names
            outcome = reconcile(spec, Dataset(columns, []), Dataset(columns, []))
            actual = Counter(r.level for r in outcome.results)
            actual["L0_snapshot"] += 1
            self.assertEqual(actual, expected_levels(spec), name)

    def test_debug_never_writes_results(self):
        data = Dataset(REPORTS["daily_revenue"].column_names, [])
        with (
            patch.object(run, "get_legacy_connection", return_value=MagicMock()),
            patch.object(run, "get_pg_connection", return_value=MagicMock()),
            patch.object(run, "fetch_dataset", return_value=data),
            patch.object(run, "write_outcome") as writer,
        ):
            result = run.run_report("daily_revenue", "debug", {"ok": False}, ignore_snapshot=True)
        writer.assert_not_called()
        self.assertEqual(result["status"], "SKIP")

    def test_all_skip_cli_exits_nonzero(self):
        summaries = {"report": "daily_revenue", "status": "SKIP", "diff_rows": 0, "failed_checks": []}
        with (
            patch.object(sys, "argv", ["reconciliation"]),
            patch.object(run, "check_snapshot", return_value={"ok": False, "reason": "mismatch"}),
            patch.object(run, "run_report", return_value=summaries),
            patch("reconciliation.lifecycle.begin_run"),
            patch(
                "reconciliation.lifecycle.finish_run", return_value={"status": "SKIP", "eligible_for_cutover": False}
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertNotEqual(run.main(), 0)

    def test_decimal_scale_drift_is_rejected(self):
        rows = [(name, *fields, 0 if fields[0] == "datetime2" else None) for name, fields in CONTRACT["orders"].items()]
        rows.append(("row_ver", "timestamp", None, None, None, "NO", None))
        self.assertEqual(schema_differences(rows, "orders"), [])
        changed = [(*r[:4], 3, *r[5:]) if r[0] == "total_amount" else r for r in rows]
        self.assertTrue(schema_differences(changed, "orders"))

    def test_reject_manifest_digest_mismatch(self):
        with self.assertRaises(ValueError):
            validate_manifest(f"manifests/{digest(b'original')}.json", b"changed")

    def test_invalid_readiness_days_and_future_date(self):
        today = date(2026, 10, 14)
        with self.assertRaises(ValueError):
            evaluate(5, today, today, 0)
        self.assertTrue(evaluate(5, date(2026, 10, 15), today, 5))

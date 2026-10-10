import sys
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reconciliation.compare import FAIL, PASS, WARN, Dataset, reconcile
from reconciliation.specs import REPORTS


def statuses(outcome):
    return {(r.level, r.name): r.status for r in outcome.results}


def by_level(outcome, level):
    return [r for r in outcome.results if r.level == level]


DAILY_COLS = ["revenue_date", "order_count", "gross_revenue"]


def daily(rows):
    return Dataset(DAILY_COLS, [
        {"revenue_date": d, "order_count": c, "gross_revenue": Decimal(v)} for d, c, v in rows
    ])


class DailyRevenueTests(unittest.TestCase):
    spec = REPORTS["daily_revenue"]

    def test_identical_tables_pass_all_levels(self):
        data = [(date(2026, 4, 1), 3, "100.00"), (date(2026, 4, 2), 1, "50.50")]
        outcome = reconcile(self.spec, daily(data), daily(data))
        self.assertEqual(outcome.status, PASS)
        self.assertEqual(
            {r.level for r in outcome.results},
            {"L1_row_count", "L2_aggregate", "L3_group", "L4_row", "L5_checksum"},
        )

    def test_driver_types_are_normalized(self):
        # pymssql có thể trả datetime/float, psycopg trả date/Decimal: phải coi là bằng nhau
        legacy = Dataset(DAILY_COLS, [{"revenue_date": datetime(2026, 4, 1, 0, 0),
                                       "order_count": 3, "gross_revenue": 100.1}])
        new = daily([(date(2026, 4, 1), 3, "100.10")])
        self.assertEqual(reconcile(self.spec, legacy, new).status, PASS)

    def test_difference_within_tolerance_is_pass_but_checksum_warns(self):
        legacy = daily([(date(2026, 4, 1), 3, "100.00")])
        new = daily([(date(2026, 4, 1), 3, "100.01")])
        outcome = reconcile(self.spec, legacy, new)
        self.assertEqual(by_level(outcome, "L4_row")[0].status, PASS)
        self.assertEqual(by_level(outcome, "L5_checksum")[0].status, WARN)
        self.assertEqual(outcome.status, WARN)

    def test_timezone_shift_keeps_totals_but_fails_row_level(self):
        # Cùng tổng tiền, nhưng doanh thu bị dời sang ngày hôm sau (lỗi UTC -> giờ VN)
        legacy = daily([(date(2026, 4, 1), 2, "100.00"), (date(2026, 4, 2), 1, "50.00")])
        new = daily([(date(2026, 4, 1), 1, "60.00"), (date(2026, 4, 2), 2, "90.00")])
        outcome = reconcile(self.spec, legacy, new)
        s = statuses(outcome)
        self.assertEqual(s[("L1_row_count", "count(*)")], PASS)
        self.assertEqual(s[("L2_aggregate", "sum(gross_revenue)")], PASS)
        self.assertEqual(s[("L3_group", "theo tháng")], PASS)
        self.assertEqual(s[("L4_row", "so từng khóa")], FAIL)
        self.assertEqual(by_level(outcome, "L4_row")[0].diff_count, 2)

    def test_missing_and_extra_rows(self):
        legacy = daily([(date(2026, 4, 1), 1, "10.00"), (date(2026, 4, 2), 1, "10.00")])
        new = daily([(date(2026, 4, 2), 1, "10.00"), (date(2026, 4, 3), 1, "10.00")])
        outcome = reconcile(self.spec, legacy, new)
        kinds = sorted(d.diff_type for d in outcome.diffs)
        self.assertEqual(kinds, ["only_in_legacy", "only_in_new"])
        self.assertEqual(outcome.status, FAIL)

    def test_duplicate_key_fails(self):
        legacy = daily([(date(2026, 4, 1), 1, "10.00")])
        new = daily([(date(2026, 4, 1), 1, "10.00"), (date(2026, 4, 1), 1, "10.00")])
        outcome = reconcile(self.spec, legacy, new)
        self.assertIn("duplicate_key", {d.diff_type for d in outcome.diffs})
        self.assertEqual(by_level(outcome, "L4_row")[0].status, FAIL)


class SegmentTests(unittest.TestCase):
    spec = REPORTS["customer_segments"]

    def test_segment_distribution_change_is_reported_by_group(self):
        cols = ["customer_id", "segment"]
        legacy = Dataset(cols, [{"customer_id": 1, "segment": "VIP"},
                                {"customer_id": 2, "segment": "DORMANT"}])
        new = Dataset(cols, [{"customer_id": 1, "segment": "VIP"},
                             {"customer_id": 2, "segment": "VIP"}])
        outcome = reconcile(self.spec, legacy, new)
        group = by_level(outcome, "L3_group")[0]
        self.assertEqual(group.status, FAIL)
        self.assertEqual({g["group"] for g in group.details["mismatched_groups"]}, {"DORMANT", "VIP"})

    def test_unicode_and_whitespace_are_normalized(self):
        cols = ["customer_id", "segment"]
        legacy = Dataset(cols, [{"customer_id": 1, "segment": "VIP  "}])
        new = Dataset(cols, [{"customer_id": 1, "segment": "VIP"}])
        self.assertEqual(reconcile(self.spec, legacy, new).status, PASS)


class TopProductsTests(unittest.TestCase):
    spec = REPORTS["top_products_by_category"]
    cols = ["category", "rank_in_category", "product_id", "product_name", "revenue"]

    def row(self, rank, pid, revenue):
        return {"category": "Điện tử", "rank_in_category": rank, "product_id": pid,
                "product_name": f"SP {pid}", "revenue": Decimal(revenue)}

    def test_tie_on_revenue_is_warning_not_failure(self):
        legacy = Dataset(self.cols, [self.row(1, 10, "500"), self.row(2, 11, "300")])
        new = Dataset(self.cols, [self.row(1, 10, "500"), self.row(2, 12, "300")])
        outcome = reconcile(self.spec, legacy, new)
        self.assertEqual(by_level(outcome, "L4_row")[0].status, WARN)
        self.assertEqual(outcome.status, WARN)

    def test_different_revenue_is_failure(self):
        legacy = Dataset(self.cols, [self.row(1, 10, "500")])
        new = Dataset(self.cols, [self.row(1, 12, "400")])
        self.assertEqual(reconcile(self.spec, legacy, new).status, FAIL)


class PivotTests(unittest.TestCase):
    spec = REPORTS["category_monthly_revenue"]

    def test_same_pivot_passes(self):
        cols = ["category", "2026-04", "2026-05"]
        rows = [{"category": "A", "2026-04": Decimal("1.00"), "2026-05": None}]
        self.assertEqual(reconcile(self.spec, Dataset(cols, rows), Dataset(cols, rows)).status, PASS)

    def test_null_is_not_zero_and_month_columns_are_compared(self):
        legacy = Dataset(["category", "2026-04", "2026-05"],
                         [{"category": "A", "2026-04": Decimal("1.00"), "2026-05": None}])
        new = Dataset(["category", "2026-04", "2026-05", "2026-06"],
                      [{"category": "A", "2026-04": Decimal("1.00"), "2026-05": Decimal("0"),
                        "2026-06": None}])
        outcome = reconcile(self.spec, legacy, new)
        s = statuses(outcome)
        self.assertEqual(s[("L1_row_count", "tập cột tháng")], FAIL)
        diff_types = {(d.diff_type, d.key.get("year_month")) for d in outcome.diffs}
        self.assertIn(("value", "2026-05"), diff_types)
        self.assertIn(("only_in_new", "2026-06"), diff_types)


if __name__ == "__main__":
    unittest.main()
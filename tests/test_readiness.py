import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reconciliation.readiness import evaluate

TODAY = date(2026, 10, 20)


class EvaluateTests(unittest.TestCase):
    def test_ready_when_streak_long_enough_and_recent(self):
        self.assertEqual(evaluate(5, date(2026, 10, 20), TODAY, required=5), [])

    def test_yesterday_still_counts_as_recent(self):
        self.assertEqual(evaluate(6, date(2026, 10, 19), TODAY, required=5), [])

    def test_not_ready_when_streak_too_short(self):
        self.assertEqual(evaluate(2, date(2026, 10, 20), TODAY, required=5), ["mới có 2/5 ngày xanh liên tiếp"])

    def test_not_ready_when_latest_day_is_not_green(self):
        problems = evaluate(0, date(2026, 10, 20), TODAY, required=5)
        self.assertEqual(problems, ["ngày chạy gần nhất (2026-10-20) chưa xanh"])

    def test_not_ready_when_pipeline_stopped(self):
        problems = evaluate(5, date(2026, 10, 17), TODAY, required=5)
        self.assertEqual(len(problems), 1)
        self.assertIn("2026-10-17", problems[0])

    def test_not_ready_without_any_run(self):
        self.assertEqual(evaluate(0, None, TODAY, required=5), ["chưa có lần đối soát nào trong recon.results"])


if __name__ == "__main__":
    unittest.main()

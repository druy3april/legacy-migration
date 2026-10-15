import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import report_portal


class ReportPortalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "live.json"
        self.path.write_text(json.dumps({"active": "old", "dashboards": {"old": 3, "new": 4}}))

    def test_invalid_dashboard_id_rejected(self):
        self.path.write_text(json.dumps({"active": "old", "dashboards": {"old": "3", "new": 4}}))
        with self.assertRaises(ValueError):
            report_portal.read_config(self.path)

    def test_rehearsal_cannot_bypass_live_route_gate(self):
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            report_portal.switch(self.path, "new", rehearsal=True)
        self.assertEqual(before, self.path.read_bytes())

    def test_rollback_works_without_database(self):
        config = report_portal.read_config(self.path)
        config["active"] = "new"
        self.path.write_text(json.dumps(config))
        with patch("reconciliation.db.get_pg_connection", side_effect=AssertionError("DB unavailable")):
            report_portal.switch(self.path, "old")
        self.assertEqual("old", report_portal.read_config(self.path)["active"])

    def test_short_streak_blocks_new_route_without_mutation(self):
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        pg = MagicMock()
        pg.execute.return_value.fetchone.side_effect = [(1, today, today, today), (True,)]
        before = self.path.read_bytes()
        with patch("reconciliation.db.get_pg_connection") as connect:
            connect.return_value.__enter__.return_value = pg
            with patch.dict("os.environ", {"CUTOVER_GREEN_DAYS": "5"}):
                with self.assertRaisesRegex(RuntimeError, "No-Go"):
                    report_portal.switch(self.path, "new")
        self.assertEqual(before, self.path.read_bytes())

    def test_actual_http_rehearsal_preserves_shared_route(self):
        before = self.path.read_bytes()
        output = Path(self.temporary.name) / "evidence.json"
        with patch.object(report_portal, "DEFAULT_CONFIG", self.path):
            report_portal.rehearse(output)
        result = json.loads(output.read_text())
        self.assertTrue(result["passed"])
        self.assertEqual(["old", "new", "old"], [step["side"] for step in result["steps"]])
        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()

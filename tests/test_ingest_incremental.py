import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ingest_incremental import DeleteGuardError, guard_delete_ratio


class GuardDeleteRatioTests(unittest.TestCase):
    def test_rejects_empty_source_when_raw_has_rows(self) -> None:
        with self.assertRaises(DeleteGuardError) as raised:
            guard_delete_ratio("customers", to_delete=59911, active=59911)
        self.assertEqual(
            str(raised.exception),
            "[customers] định đánh dấu xóa 59911/59911 dòng (100.0%), "
            "vượt ngưỡng 5%. Kiểm tra nguồn rồi chạy lại với "
            "MAX_DELETE_RATIO lớn hơn nếu đúng là xóa thật.",
        )

    def test_allows_empty_source_when_raw_is_also_empty(self) -> None:
        guard_delete_ratio("customers", to_delete=0, active=0)

    def test_allows_three_deletes_below_threshold(self) -> None:
        guard_delete_ratio("order_items", to_delete=3, active=59911)

    def test_allows_ratio_at_threshold(self) -> None:
        guard_delete_ratio(
            "orders",
            to_delete=5,
            active=100,
            max_delete_ratio=0.05,
        )


if __name__ == "__main__":
    unittest.main()

"""Logic so sánh thuần (không chạm database) để dễ viết unit test.

Năm cấp độ:
  L1_row_count  số dòng
  L2_aggregate  SUM / MIN / MAX từng cột
  L3_group      số dòng + tổng tiền theo nhóm
  L4_row        từng khóa: chỉ có ở một phía, hoặc giá trị khác
  L5_checksum   băm các dòng đã chuẩn hóa (toàn bảng + 16 bucket)
"""
import hashlib
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from reconciliation.specs import ReportSpec

CENT = Decimal("0.01")
DEFAULT_TOLERANCE = Decimal("0.01")
MAX_DETAILS = 20        # số nhóm/dòng lệch tối đa ghi vào details
BUCKETS = 16

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"


@dataclass
class Dataset:
    columns: list[str]
    rows: list[dict[str, Any]]


@dataclass
class CheckResult:
    report: str
    level: str
    name: str
    status: str
    legacy_value: str | None = None
    new_value: str | None = None
    diff_count: int = 0
    tolerance: Decimal | None = None
    details: dict | None = None


@dataclass
class RowDiff:
    report: str
    key: dict[str, Any]
    diff_type: str          # only_in_legacy | only_in_new | value | tie | duplicate_key
    column: str | None = None
    legacy_value: Any = None
    new_value: Any = None


@dataclass
class ReportOutcome:
    report: str
    results: list[CheckResult] = field(default_factory=list)
    diffs: list[RowDiff] = field(default_factory=list)

    @property
    def status(self) -> str:
        return worst([r.status for r in self.results])


def worst(statuses: list[str]) -> str:
    rank = {PASS: 0, WARN: 1, SKIP: 2, FAIL: 3}
    return max(statuses, key=lambda s: rank[s], default=PASS)


# ---------------------------------------------------------------- chuẩn hóa

def normalize_value(kind: str, value: Any) -> Any:
    if value is None:
        return None
    if kind == "int":
        return int(value)
    if kind == "money":
        # Đi qua str để float 0.1 không thành 0.1000000000000000055...
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    if kind == "date":
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]
    if kind == "text":
        return unicodedata.normalize("NFC", str(value)).strip()
    raise ValueError(kind)


def normalize_rows(spec: ReportSpec, rows: list[dict]) -> list[dict]:
    return [
        {c.name: normalize_value(c.kind, row.get(c.name)) for c in spec.columns}
        for row in rows
    ]


def unpivot(dataset: Dataset, id_column: str) -> tuple[list[dict], list[str]]:
    """Bảng ngang (category, "2026-04", "2026-05", ...) -> dạng dọc (category, year_month, revenue)."""
    value_columns = [c for c in dataset.columns if c != id_column]
    long_rows = [
        {id_column: row[id_column], "year_month": col, "revenue": row[col]}
        for row in dataset.rows
        for col in value_columns
    ]
    return long_rows, sorted(value_columns)


def values_equal(kind: str, a: Any, b: Any, tolerance: Decimal) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if kind == "money":
        return abs(a - b) <= tolerance
    return a == b


def _fmt(value: Any) -> str | None:
    return None if value is None else str(value)


# ---------------------------------------------------------------- các cấp so sánh

def check_row_count(spec: ReportSpec, legacy: list[dict], new: list[dict]) -> CheckResult:
    diff = abs(len(legacy) - len(new))
    return CheckResult(
        spec.name, "L1_row_count", "count(*)",
        PASS if diff == 0 else FAIL,
        str(len(legacy)), str(len(new)), diff,
    )


def _aggregates(kind: str, values: list[Any]) -> dict[str, Any]:
    present = [v for v in values if v is not None]
    aggs: dict[str, Any] = {"nulls": len(values) - len(present)}
    if kind in ("int", "money"):
        aggs["sum"] = sum(present) if present else None
    if kind == "text":
        aggs["count_distinct"] = len(set(present))
    else:
        aggs["min"] = min(present) if present else None
        aggs["max"] = max(present) if present else None
    return aggs


def check_aggregates(
    spec: ReportSpec, legacy: list[dict], new: list[dict], tolerance: Decimal
) -> list[CheckResult]:
    results = []
    for col in spec.value_columns:
        if col.name in spec.tie_columns:
            continue  # cột có thể đổi khi hòa hạng: để L4 phân loại tie, không cộng ID
        old_aggs = _aggregates(col.kind, [r[col.name] for r in legacy])
        new_aggs = _aggregates(col.kind, [r[col.name] for r in new])
        for agg_name, old_value in old_aggs.items():
            new_value = new_aggs[agg_name]
            kind = col.kind if agg_name in ("sum", "min", "max") else "int"
            ok = values_equal(kind, old_value, new_value, tolerance)
            results.append(CheckResult(
                spec.name, "L2_aggregate", f"{agg_name}({col.name})",
                PASS if ok else FAIL, _fmt(old_value), _fmt(new_value),
                0 if ok else 1,
                tolerance if kind == "money" else None,
            ))
    return results


def _group_stats(spec: ReportSpec, rows: list[dict]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"rows": 0, **{m: Decimal("0") for m in spec.measures}}
    )
    for row in rows:
        group = spec.group_by(row)
        stats[group]["rows"] += 1
        for m in spec.measures:
            if row[m] is not None:
                stats[group][m] += row[m]
    return stats


def check_groups(
    spec: ReportSpec, legacy: list[dict], new: list[dict], tolerance: Decimal
) -> CheckResult:
    if spec.group_by is None:
        return CheckResult(spec.name, "L3_group", "không cấu hình nhóm", SKIP)
    old_stats, new_stats = _group_stats(spec, legacy), _group_stats(spec, new)
    mismatched = []
    for group in sorted(set(old_stats) | set(new_stats)):
        old = old_stats.get(group)
        cur = new_stats.get(group)
        same = (
            old is not None and cur is not None
            and old["rows"] == cur["rows"]
            and all(values_equal("money", old[m], cur[m], tolerance) for m in spec.measures)
        )
        if not same:
            mismatched.append({
                "group": group,
                "legacy": {k: _fmt(v) for k, v in (old or {}).items()},
                "new": {k: _fmt(v) for k, v in (cur or {}).items()},
            })
    return CheckResult(
        spec.name, "L3_group", spec.group_label,
        PASS if not mismatched else FAIL,
        str(len(old_stats)), str(len(new_stats)), len(mismatched), tolerance,
        {"mismatched_groups": mismatched[:MAX_DETAILS]} if mismatched else None,
    )


def _index(spec: ReportSpec, rows: list[dict], side: str, diffs: list[RowDiff]) -> dict[tuple, dict]:
    index: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row[k] for k in spec.keys)
        if key in index:
            # column ghi phía bị trùng khóa: legacy hoặc new
            diffs.append(RowDiff(spec.name, dict(zip(spec.keys, key)), "duplicate_key", side))
        index[key] = row
    return index


def check_rows(
    spec: ReportSpec, legacy: list[dict], new: list[dict], tolerance: Decimal
) -> tuple[CheckResult, list[RowDiff]]:
    diffs: list[RowDiff] = []
    old_index = _index(spec, legacy, "legacy", diffs)
    new_index = _index(spec, new, "new", diffs)
    bad_keys: set[tuple] = set()
    tie_keys: set[tuple] = set()

    for key in sorted(set(old_index) | set(new_index), key=lambda k: tuple(_fmt(v) or "" for v in k)):
        key_dict = dict(zip(spec.keys, key))
        old, cur = old_index.get(key), new_index.get(key)
        if cur is None:
            diffs.append(RowDiff(spec.name, key_dict, "only_in_legacy"))
            bad_keys.add(key)
            continue
        if old is None:
            diffs.append(RowDiff(spec.name, key_dict, "only_in_new"))
            bad_keys.add(key)
            continue
        changed = [
            c for c in spec.value_columns
            if not values_equal(c.kind, old[c.name], cur[c.name], tolerance)
        ]
        if not changed:
            continue
        is_tie = bool(spec.tie_columns) and {c.name for c in changed} <= set(spec.tie_columns)
        for c in changed:
            diffs.append(RowDiff(spec.name, key_dict, "tie" if is_tie else "value",
                                 c.name, old[c.name], cur[c.name]))
        (tie_keys if is_tie else bad_keys).add(key)

    has_duplicates = any(d.diff_type == "duplicate_key" for d in diffs)
    if bad_keys or has_duplicates:
        status = FAIL
    elif tie_keys:
        status = WARN
    else:
        status = PASS
    details = None
    if bad_keys or tie_keys or has_duplicates:
        counts: dict[str, int] = defaultdict(int)
        for d in diffs:
            counts[d.diff_type] += 1
        details = {"by_type": dict(counts)}
    result = CheckResult(
        spec.name, "L4_row", "so từng khóa", status,
        str(len(old_index)), str(len(new_index)),
        len(bad_keys) + len(tie_keys), tolerance, details,
    )
    return result, diffs


def _row_hash(spec: ReportSpec, row: dict) -> str:
    canonical = "|".join("∅" if row[c] is None else str(row[c]) for c in spec.column_names)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()


def _bucket(spec: ReportSpec, row: dict) -> int:
    key = "|".join(str(row[k]) for k in spec.keys)
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) % BUCKETS


def table_checksum(spec: ReportSpec, rows: list[dict]) -> tuple[str, dict[int, str]]:
    per_bucket: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        per_bucket[_bucket(spec, row)].append(_row_hash(spec, row))
    buckets = {
        b: hashlib.md5("\n".join(sorted(h)).encode()).hexdigest()
        for b, h in per_bucket.items()
    }
    total = hashlib.md5(
        "\n".join(f"{b}:{buckets[b]}" for b in sorted(buckets)).encode()
    ).hexdigest()
    return total, buckets


def check_checksum(spec: ReportSpec, legacy: list[dict], new: list[dict], row_status: str) -> CheckResult:
    old_total, old_buckets = table_checksum(spec, legacy)
    new_total, new_buckets = table_checksum(spec, new)
    if old_total == new_total:
        return CheckResult(spec.name, "L5_checksum", "md5 dòng chuẩn hóa", PASS, old_total, new_total)
    bad = sorted(b for b in set(old_buckets) | set(new_buckets)
                 if old_buckets.get(b) != new_buckets.get(b))
    # Checksum so tuyệt đối; nếu L4 đã chấp nhận (lệch trong ngưỡng / hòa hạng) thì chỉ cảnh báo
    status = WARN if row_status in (PASS, WARN) else FAIL
    return CheckResult(
        spec.name, "L5_checksum", "md5 dòng chuẩn hóa", status,
        old_total, new_total, len(bad), None, {"mismatched_buckets": bad},
    )


def check_pivot_columns(spec: ReportSpec, legacy_cols: list[str], new_cols: list[str]) -> CheckResult:
    only_old = sorted(set(legacy_cols) - set(new_cols))
    only_new = sorted(set(new_cols) - set(legacy_cols))
    diff = len(only_old) + len(only_new)
    return CheckResult(
        spec.name, "L1_row_count", "tập cột tháng",
        PASS if diff == 0 else FAIL,
        ",".join(legacy_cols), ",".join(new_cols), diff, None,
        {"only_in_legacy": only_old, "only_in_new": only_new} if diff else None,
    )


# ---------------------------------------------------------------- điểm vào

def reconcile(
    spec: ReportSpec, legacy: Dataset, new: Dataset,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> ReportOutcome:
    outcome = ReportOutcome(spec.name)
    legacy_rows, new_rows = legacy.rows, new.rows

    if spec.pivot_id:
        legacy_rows, legacy_cols = unpivot(legacy, spec.pivot_id)
        new_rows, new_cols = unpivot(new, spec.pivot_id)
        outcome.results.append(check_pivot_columns(spec, legacy_cols, new_cols))

    old = normalize_rows(spec, legacy_rows)
    cur = normalize_rows(spec, new_rows)

    outcome.results.append(check_row_count(spec, old, cur))
    outcome.results.extend(check_aggregates(spec, old, cur, tolerance))
    outcome.results.append(check_groups(spec, old, cur, tolerance))
    row_result, diffs = check_rows(spec, old, cur, tolerance)
    outcome.results.append(row_result)
    outcome.diffs = diffs
    outcome.results.append(check_checksum(spec, old, cur, row_result.status))
    return outcome
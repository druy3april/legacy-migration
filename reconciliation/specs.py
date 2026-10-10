"""Khai báo cặp bảng cần đối soát: bảng báo cáo cũ (SQL Server) <-> model dbt (Postgres)."""
from collections.abc import Callable
from dataclasses import dataclass

# Kiểu cột quyết định cách chuẩn hóa và so sánh
#   int   : so bằng tuyệt đối
#   money : làm tròn 2 chữ số, so với ngưỡng sai số
#   date  : đưa về chuỗi YYYY-MM-DD
#   text  : chuẩn hóa Unicode NFC + bỏ khoảng trắng hai đầu
KINDS = {"int", "money", "date", "text"}


@dataclass(frozen=True)
class Column:
    name: str
    kind: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"Kiểu cột không hợp lệ: {self.kind}")


@dataclass(frozen=True)
class ReportSpec:
    name: str
    legacy_table: str
    new_table: str
    columns: tuple[Column, ...]          # gồm cả cột khóa
    keys: tuple[str, ...]
    group_label: str = ""                # mô tả cấp 3 (theo nhóm)
    group_by: Callable[[dict], str] | None = None
    group_measures: tuple[str, ...] = () # chỉ cộng các cột tiền này theo nhóm; rỗng = mọi cột money
    tie_columns: tuple[str, ...] = ()    # chỉ lệch ở đây, measure khớp => WARN do hòa hạng
    pivot_id: str | None = None          # cột ID được giữ nguyên khi unpivot PIVOT động
    pivot_column: str | None = None      # cột dạng dọc chứa tên các cột tháng động
    pivot_measure: str | None = None     # cột dạng dọc chứa giá trị của PIVOT động
    notes: str = ""

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def kind_of(self, name: str) -> str:
        for col in self.columns:
            if col.name == name:
                return col.kind
        raise KeyError(name)

    @property
    def value_columns(self) -> list[Column]:
        return [c for c in self.columns if c.name not in self.keys]

    @property
    def measures(self) -> list[str]:
        if self.group_measures:
            return list(self.group_measures)
        return [c.name for c in self.value_columns if c.kind == "money"]


def month_of(column: str) -> Callable[[dict], str]:
    """Nhóm theo tháng của một cột ngày đã chuẩn hóa (YYYY-MM-DD)."""
    def _group(row: dict) -> str:
        value = row[column]
        return value[:7] if value else "NULL"
    return _group


def value_of(column: str) -> Callable[[dict], str]:
    def _group(row: dict) -> str:
        value = row[column]
        return "NULL" if value is None else str(value)
    return _group


REPORTS: dict[str, ReportSpec] = {}


def _register(spec: ReportSpec) -> None:
    REPORTS[spec.name] = spec


_register(ReportSpec(
    name="daily_revenue",
    legacy_table="dbo.daily_revenue",
    new_table="marts.mart_daily_revenue",
    columns=(
        Column("revenue_date", "date"),
        Column("order_count", "int"),
        Column("gross_revenue", "money"),
    ),
    keys=("revenue_date",),
    group_label="theo tháng",
    group_by=month_of("revenue_date"),
))

_register(ReportSpec(
    name="customer_ltv",
    legacy_table="dbo.customer_ltv",
    new_table="marts.mart_customer_ltv",
    columns=(
        Column("customer_id", "int"),
        Column("order_count", "int"),
        Column("total_spent", "money"),
        Column("first_order_date", "date"),
        Column("last_order_date", "date"),
    ),
    keys=("customer_id",),
    group_label="theo tháng mua đầu tiên (cohort)",
    group_by=month_of("first_order_date"),
))

_register(ReportSpec(
    name="customer_segments",
    legacy_table="dbo.customer_segments",
    new_table="marts.mart_customer_segments",
    columns=(
        Column("customer_id", "int"),
        Column("segment", "text"),
    ),
    keys=("customer_id",),
    group_label="theo segment",
    group_by=value_of("segment"),
))

_register(ReportSpec(
    name="product_sales",
    legacy_table="dbo.product_sales",
    new_table="marts.mart_product_sales",
    columns=(
        Column("product_id", "int"),
        Column("units_sold", "int"),
        Column("revenue", "money"),
        Column("last_sold_date", "date"),
    ),
    keys=("product_id",),
    group_label="theo tháng bán gần nhất",
    group_by=month_of("last_sold_date"),
))

_register(ReportSpec(
    name="cumulative_revenue",
    legacy_table="dbo.cumulative_revenue",
    new_table="marts.mart_cumulative_revenue",
    columns=(
        Column("revenue_date", "date"),
        Column("daily_revenue", "money"),
        Column("running_total", "money"),
    ),
    keys=("revenue_date",),
    group_label="theo tháng",
    group_by=month_of("revenue_date"),
    group_measures=("daily_revenue",),  # không cộng running_total theo tháng
))

_register(ReportSpec(
    name="top_products_by_category",
    legacy_table="dbo.top_products_by_category",
    new_table="marts.mart_top_products_by_category",
    columns=(
        Column("category", "text"),
        Column("rank_in_category", "int"),
        Column("product_id", "int"),
        Column("product_name", "text"),
        Column("revenue", "money"),
    ),
    keys=("category", "rank_in_category"),
    group_label="theo danh mục",
    group_by=value_of("category"),
    tie_columns=("product_id", "product_name"),
    notes=(
        "Procedure cũ không quy định tie-break; chỉ lệch product_id/product_name "
        "khi revenue khớp thì WARN."
    ),
))

_register(ReportSpec(
    name="category_monthly_revenue",
    legacy_table="dbo.category_monthly_revenue",
    new_table="marts.mart_category_monthly_revenue",
    columns=(
        Column("category", "text"),
        Column("year_month", "text"),
        Column("revenue", "money"),
    ),
    keys=("category", "year_month"),
    group_label="theo tháng",
    group_by=value_of("year_month"),
    pivot_id="category",
    pivot_column="year_month",
    pivot_measure="revenue",
    notes=(
        "Unpivot hai phía về (category, year_month, revenue), so cả tập cột tháng; "
        "NULL khác 0 (ADR-0003)."
    ),
))
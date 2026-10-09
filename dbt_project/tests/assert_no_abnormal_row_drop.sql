-- Số dòng của mart không được giảm quá 10% so với lần chạy thành công trước
-- (audit.row_counts được ghi ở on-run-end, xem macros/row_count_audit.sql)
{{ config(severity = 'error') }}

with previous as (
    select model_name, row_count
    from audit.row_counts
    where run_at = (select max(run_at) from audit.row_counts)
),
current_counts as (
    select 'mart_daily_revenue' as model_name, count(*) as row_count from {{ ref('mart_daily_revenue') }}
    union all
    select 'mart_customer_ltv', count(*) from {{ ref('mart_customer_ltv') }}
    union all
    select 'mart_product_sales', count(*) from {{ ref('mart_product_sales') }}
)
select c.model_name, p.row_count as previous_count, c.row_count as current_count
from current_counts as c
join previous as p using (model_name)
where c.row_count < p.row_count * 0.9
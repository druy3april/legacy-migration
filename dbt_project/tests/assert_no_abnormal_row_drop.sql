-- Số dòng của mart không được giảm quá 10% so với lần chạy thành công trước
-- (audit.row_counts được ghi ở on-run-end, xem macros/row_count_audit.sql)
{{ config(severity = 'error') }}

with previous as (
    select distinct on (rc.model_name)
        rc.model_name,
        rc.row_count
    from audit.row_counts as rc
    order by rc.model_name asc, rc.run_at desc
),

current_counts as (
    select
        'mart_daily_revenue' as model_name,
        count(*) as row_count
    from {{ ref('mart_daily_revenue') }}
    union all
    select
        'mart_customer_ltv' as model_name,
        count(*) as row_count
    from {{ ref('mart_customer_ltv') }}
    union all
    select
        'mart_product_sales' as model_name,
        count(*) as row_count
    from {{ ref('mart_product_sales') }}
)

select
    c.model_name,
    p.row_count as previous_count,
    c.row_count as current_count
from current_counts as c
inner join previous as p on c.model_name = p.model_name
where c.row_count < p.row_count * 0.9

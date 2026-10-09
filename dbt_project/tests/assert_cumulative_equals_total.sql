-- Lũy kế ngày cuối phải bằng tổng doanh thu mọi ngày
with last_day as (
    select running_total
    from {{ ref('mart_cumulative_revenue') }}
    order by revenue_date desc
    limit 1
),
total as (
    select sum(gross_revenue) as total from {{ ref('mart_daily_revenue') }}
)
select *
from last_day cross join total
where last_day.running_total <> total.total
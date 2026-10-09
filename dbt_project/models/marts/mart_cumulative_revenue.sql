-- Thay cho dbo.sp_refresh_cumulative_revenue (WHILE đi từng ngày)
-- Điểm dễ sai: vòng WHILE đi qua MỌI ngày từ min đến max, kể cả ngày không có đơn (daily = 0).
-- Vì vậy cần bảng lịch (date spine) rồi mới cộng dồn bằng window function.
with bounds as (
    select min(revenue_date) as first_day, max(revenue_date) as last_day
    from {{ ref('mart_daily_revenue') }}
),

date_spine as (
    select gs::date as revenue_date
    from bounds
    cross join generate_series(bounds.first_day, bounds.last_day, interval '1 day') as gs
),

daily as (
    select
        s.revenue_date,
        coalesce(d.gross_revenue, 0)::numeric(18, 2) as daily_revenue
    from date_spine as s
    left join {{ ref('mart_daily_revenue') }} as d
        on d.revenue_date = s.revenue_date
)

select
    revenue_date,
    daily_revenue,
    sum(daily_revenue) over (
        order by revenue_date
        rows between unbounded preceding and current row
    )::numeric(18, 2) as running_total
from daily
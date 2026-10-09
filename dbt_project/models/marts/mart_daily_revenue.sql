-- Thay cho dbo.sp_refresh_daily_revenue (TRUNCATE + INSERT -> model table)
-- Lưu ý: chỉ loại CANCELLED, nên đơn NEW vẫn được tính (khác customer_ltv)
select
    order_day                        as revenue_date,
    count(*)::int                    as order_count,
    sum(total_amount)::numeric(18, 2) as gross_revenue
from {{ ref('stg_orders') }}
where status <> 'CANCELLED'
group by order_day
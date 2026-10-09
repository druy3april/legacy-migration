-- Thay cho dbo.sp_refresh_customer_ltv: 2 bảng tạm #order_totals, #ltv_all -> 2 CTE
with order_totals as (
    select
        customer_id,
        count(*)          as order_count,
        sum(total_amount) as total_spent,
        min(order_date)   as first_order,
        max(order_date)   as last_order
    from {{ ref('stg_orders') }}
    where {{ in_list('status', var('paid_statuses')) }}
    group by customer_id
)

select
    c.customer_id,
    coalesce(t.order_count, 0)::int            as order_count,   -- ISNULL -> COALESCE
    coalesce(t.total_spent, 0)::numeric(18, 2) as total_spent,
    t.first_order::date                        as first_order_date,  -- CONVERT(DATE, ...)
    t.last_order::date                         as last_order_date
from {{ ref('stg_customers') }} as c
left join order_totals as t
    on t.customer_id = c.customer_id
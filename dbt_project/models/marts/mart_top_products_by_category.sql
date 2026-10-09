-- Thay cho dbo.sp_refresh_top_products_by_category (#product_revenue, #top3, CROSS APPLY TOP 3)
-- CROSS APPLY + TOP (3) + ROW_NUMBER -> một window function rồi lọc rank <= 3 (TOP n -> LIMIT/filter)
with product_revenue as (
    select
        p.product_id,
        p.category,
        p.product_name,
        sum(oi.line_amount) as revenue
    from {{ ref('stg_order_items') }} as oi
    join {{ ref('stg_orders') }}   as o on o.order_id   = oi.order_id
    join {{ ref('stg_products') }} as p on p.product_id = oi.product_id
    where {{ in_list('o.status', var('paid_statuses')) }}
    group by p.product_id, p.category, p.product_name
),

ranked as (
    select
        *,
        -- product_id để phá hòa: procedure gốc không xác định thứ tự khi bằng doanh thu
        row_number() over (partition by category order by revenue desc, product_id) as rank_in_category
    from product_revenue
)

select
    category,
    rank_in_category::int,
    product_id,
    product_name,
    revenue::numeric(18, 2) as revenue
from ranked
where rank_in_category <= 3
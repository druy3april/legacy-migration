-- Dạng dọc (long) của doanh thu danh mục x tháng: dễ test, dễ đối soát, không đổi số cột
select
    p.category,
    to_char(o.order_date, 'YYYY-MM')     as year_month,   -- CONVERT(CHAR(7), order_date, 126)
    sum(oi.line_amount)::numeric(18, 2)  as revenue
from {{ ref('stg_order_items') }} as oi
join {{ ref('stg_orders') }}   as o on o.order_id   = oi.order_id
join {{ ref('stg_products') }} as p on p.product_id = oi.product_id
where {{ in_list('o.status', var('paid_statuses')) }}
group by p.category, to_char(o.order_date, 'YYYY-MM')
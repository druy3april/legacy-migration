-- Dạng dọc (long) của doanh thu danh mục x tháng: dễ test, dễ đối soát, không đổi số cột
select
    p.category,
    -- CONVERT(CHAR(7), order_date, 126); giữ tên cột year_month cho khớp báo cáo cũ
    to_char(o.order_date, 'YYYY-MM') as year_month,  -- noqa: RF04
    sum(oi.line_amount)::numeric(18, 2) as revenue
from {{ ref('stg_order_items') }} as oi
inner join {{ ref('stg_orders') }} as o on oi.order_id = o.order_id
inner join {{ ref('stg_products') }} as p on oi.product_id = p.product_id
where {{ in_list('o.status', var('paid_statuses')) }}
group by p.category, to_char(o.order_date, 'YYYY-MM')

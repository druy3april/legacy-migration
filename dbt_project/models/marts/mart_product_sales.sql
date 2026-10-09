-- Thay cho dbo.sp_refresh_product_sales (biến bảng @sales + MERGE có nhánh DELETE)
-- MERGE ... WHEN NOT MATCHED BY SOURCE THEN DELETE = kết quả cuối cùng giống hệt tính lại toàn bộ,
-- nên model table là cách chuyển đúng nhất. Xem bài tập incremental trong migration_notes.md
select
    oi.product_id,
    sum(oi.quantity)::int                as units_sold,
    sum(oi.line_amount)::numeric(18, 2)  as revenue,
    max(o.order_date)::date              as last_sold_date
from {{ ref('stg_order_items') }} as oi
join {{ ref('stg_orders') }} as o
    on o.order_id = oi.order_id
where {{ in_list('o.status', var('paid_statuses')) }}
group by oi.product_id
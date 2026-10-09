select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price::numeric(12, 2) as unit_price,
    (quantity * unit_price)::numeric(18, 2) as line_amount,
    row_ver
from {{ source('raw', 'order_items') }}
where _deleted_at is null
select
    order_id,
    customer_id,
    order_date,                       -- TIMESTAMP không múi giờ, giống DATETIME2 ở nguồn
    order_date::date as order_day,    -- tương đương CAST(order_date AS DATE)
    upper(trim(status)) as status,
    total_amount::numeric(14, 2) as total_amount,
    updated_at,
    row_ver
from {{ source('raw', 'orders') }}
where _deleted_at is null
select
    product_id,
    product_name,
    category,
    unit_price::numeric(12, 2) as unit_price,
    is_active,
    created_at,
    row_ver
from {{ source('raw', 'products') }}
where _deleted_at is null
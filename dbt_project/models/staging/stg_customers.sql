select
    customer_id,
    full_name,
    email,
    city,
    created_at,
    row_ver
from {{ source('raw', 'customers') }}
where _deleted_at is null
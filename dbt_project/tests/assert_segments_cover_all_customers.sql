-- Mỗi khách hiện hành phải có đúng một phân khúc (cursor cũ duyệt toàn bộ customer_ltv)
select c.customer_id
from {{ ref('stg_customers') }} as c
left join {{ ref('mart_customer_segments') }} as s
    on c.customer_id = s.customer_id
where s.customer_id is null

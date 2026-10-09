-- Thay cho dbo.sp_refresh_customer_segments: CURSOR + IF/ELSE IF -> một CASE WHEN theo tập hợp
-- Thứ tự WHEN phải giữ đúng thứ tự IF/ELSE IF trong procedure
select
    customer_id,
    case
        when order_count = 0 then 'INACTIVE'
        -- DATEDIFF(DAY, last, as_of) trên kiểu DATE = phép trừ hai date trong Postgres
        when (date '{{ var("segment_as_of") }}' - last_order_date) > {{ var('dormant_days') }} then 'DORMANT'
        when total_spent >= {{ var('vip_threshold') }} then 'VIP'
        when total_spent >= {{ var('regular_threshold') }} then 'REGULAR'
        else 'CASUAL'
    end::varchar(20) as segment
from {{ ref('mart_customer_ltv') }}
with expected as (
    select sum(total_amount)::numeric(18, 2) as revenue
    from {{ ref('stg_orders') }}
    where status <> 'CANCELLED'
),

actual as (
    select sum(gross_revenue)::numeric(18, 2) as revenue
    from {{ ref('mart_daily_revenue') }}
)

select 1
from expected
cross join actual
where expected.revenue is distinct from actual.revenue

with expected as (
    select
        revenue_date,
        sum(daily_revenue) over (
            order by revenue_date
            rows between unbounded preceding and current row
        ) as running_total
    from {{ ref('mart_cumulative_revenue') }}
)

select actual.revenue_date
from {{ ref('mart_cumulative_revenue') }} as actual
inner join expected on actual.revenue_date = expected.revenue_date
where actual.running_total is distinct from expected.running_total

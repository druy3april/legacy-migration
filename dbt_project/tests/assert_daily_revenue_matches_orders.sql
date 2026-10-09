WITH expected AS (
    SELECT SUM(total_amount)::numeric(18, 2) AS revenue
    FROM {{ ref('stg_orders') }}
    WHERE status <> 'CANCELLED'
),
actual AS (
    SELECT SUM(gross_revenue)::numeric(18, 2) AS revenue
    FROM {{ ref('mart_daily_revenue') }}
)
SELECT 1
FROM expected
CROSS JOIN actual
WHERE expected.revenue IS DISTINCT FROM actual.revenue

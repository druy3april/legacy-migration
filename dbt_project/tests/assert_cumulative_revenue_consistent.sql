WITH expected AS (
    SELECT
        revenue_date,
        SUM(daily_revenue) OVER (
            ORDER BY revenue_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_total
    FROM {{ ref('mart_cumulative_revenue') }}
)
SELECT actual.revenue_date
FROM {{ ref('mart_cumulative_revenue') }} AS actual
JOIN expected USING (revenue_date)
WHERE actual.running_total IS DISTINCT FROM expected.running_total

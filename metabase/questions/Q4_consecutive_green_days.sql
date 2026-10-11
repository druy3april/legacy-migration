WITH days AS (
    SELECT run_date, bool_and(status IN ('PASS', 'WARN')) AS green
    FROM recon.v_daily_status
    GROUP BY run_date
),
last_bad AS (
    SELECT max(run_date) AS d FROM days WHERE NOT green
)
SELECT count(*) AS "Số ngày xanh liên tiếp"
FROM days, last_bad
WHERE days.green AND (last_bad.d IS NULL OR days.run_date > last_bad.d);

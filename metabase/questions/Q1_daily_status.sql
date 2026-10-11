SELECT run_date AS "Ngày", status AS "Trạng thái", count(*) AS "Số báo cáo"
FROM recon.v_daily_status
GROUP BY 1, 2
ORDER BY 1, 2;

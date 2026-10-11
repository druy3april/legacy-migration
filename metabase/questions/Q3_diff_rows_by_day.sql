SELECT run_date AS "Ngày", report AS "Báo cáo", diff_rows AS "Dòng lệch"
FROM recon.v_daily_status
ORDER BY 1, 2;

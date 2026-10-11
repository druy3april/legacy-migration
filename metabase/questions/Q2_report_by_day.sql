SELECT report AS "Báo cáo", run_date AS "Ngày", status AS "Trạng thái", diff_rows AS "Dòng lệch"
FROM recon.v_daily_status
WHERE run_date >= current_date - 14
ORDER BY report, run_date;

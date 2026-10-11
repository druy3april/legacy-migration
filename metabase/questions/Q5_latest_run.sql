SELECT report AS "Báo cáo", check_level AS "Cấp", check_name AS "Kiểm tra",
       legacy_value AS "Hệ thống cũ", new_value AS "Hệ thống mới",
       diff_count AS "Số lệch", status AS "Trạng thái"
FROM recon.v_latest_run
WHERE status <> 'PASS'
ORDER BY report, check_level;

SELECT d.report AS "Báo cáo", d.key::text AS "Khóa", d.diff_type AS "Loại lệch",
       d.column_name AS "Cột", d.legacy_value AS "Cũ", d.new_value AS "Mới"
FROM recon.row_diffs AS d
WHERE d.run_id = (
    SELECT run_id FROM recon.v_report_status WHERE status = 'FAIL'
    ORDER BY checked_at DESC LIMIT 1
)
ORDER BY d.report, d.id
LIMIT 200;

-- Kết quả kỳ vọng của dbt build trên ci/sample_raw_data.sql (golden test).
-- Test schema của dbt chỉ kiểm tra ràng buộc; file này kiểm tra con số nghiệp vụ, nên bắt được
-- lỗi kiểu "tổng vẫn đúng nhưng phân bổ sai" (ví dụ Ca 1 đổi múi giờ trong docs/reconciliation.md).
-- Số kỳ vọng được tính lại từ logic stored procedure; sai một mục là CI đỏ.

DO $$
DECLARE
    actual   text;
    failures text := '';
BEGIN
    EXECUTE 'select count(*)::text from marts.mart_daily_revenue' INTO actual;
    IF actual IS DISTINCT FROM '6' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_daily_revenue: số dòng', '6', actual);
    END IF;

    EXECUTE 'select string_agg(revenue_date || ''='' || gross_revenue, '','' order by revenue_date) from marts.mart_daily_revenue' INTO actual;
    IF actual IS DISTINCT FROM '2026-07-15=8150000.00,2026-08-10=84850000.00,2026-08-12=3100000.00,2026-09-01=167800000.00,2026-09-15=52800000.00,2026-09-20=97800000.00' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_daily_revenue: doanh thu từng ngày', '2026-07-15=8150000.00,2026-08-10=84850000.00,2026-08-12=3100000.00,2026-09-01=167800000.00,2026-09-15=52800000.00,2026-09-20=97800000.00', actual);
    END IF;

    EXECUTE 'select sum(gross_revenue)::text from marts.mart_daily_revenue' INTO actual;
    IF actual IS DISTINCT FROM '414500000.00' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_daily_revenue: tổng doanh thu', '414500000.00', actual);
    END IF;

    EXECUTE 'select count(*)::text from marts.mart_cumulative_revenue' INTO actual;
    IF actual IS DISTINCT FROM '68' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_cumulative_revenue: số ngày (có date spine)', '68', actual);
    END IF;

    EXECUTE 'select running_total::text from marts.mart_cumulative_revenue order by revenue_date desc limit 1' INTO actual;
    IF actual IS DISTINCT FROM '414500000.00' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_cumulative_revenue: lũy kế cuối', '414500000.00', actual);
    END IF;

    EXECUTE 'select count(*)::text from marts.mart_customer_ltv' INTO actual;
    IF actual IS DISTINCT FROM '7' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_customer_ltv: số khách hiện hành', '7', actual);
    END IF;

    EXECUTE 'select sum(total_spent)::text from marts.mart_customer_ltv' INTO actual;
    IF actual IS DISTINCT FROM '412400000.00' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_customer_ltv: tổng chi tiêu', '412400000.00', actual);
    END IF;

    EXECUTE 'select string_agg(segment || ''='' || n, '','' order by segment) from (select segment, count(*) n from marts.mart_customer_segments group by segment) s' INTO actual;
    IF actual IS DISTINCT FROM 'CASUAL=2,DORMANT=1,INACTIVE=2,REGULAR=1,VIP=1' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_customer_segments: phân bố', 'CASUAL=2,DORMANT=1,INACTIVE=2,REGULAR=1,VIP=1', actual);
    END IF;

    EXECUTE 'select count(*)::text from marts.mart_product_sales' INTO actual;
    IF actual IS DISTINCT FROM '7' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_product_sales: số sản phẩm đã bán', '7', actual);
    END IF;

    EXECUTE 'select sum(revenue)::text from marts.mart_product_sales' INTO actual;
    IF actual IS DISTINCT FROM '412400000.00' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_product_sales: tổng doanh thu', '412400000.00', actual);
    END IF;

    EXECUTE 'select count(*)::text from marts.mart_top_products_by_category' INTO actual;
    IF actual IS DISTINCT FROM '6' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_top_products_by_category: số dòng', '6', actual);
    END IF;

    EXECUTE 'select sum(revenue)::text from marts.mart_top_products_by_category' INTO actual;
    IF actual IS DISTINCT FROM '405200000.00' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_top_products_by_category: tổng doanh thu', '405200000.00', actual);
    END IF;

    EXECUTE 'select string_agg(product_id::text, '','' order by rank_in_category) from marts.mart_top_products_by_category where category = ''Điện tử''' INTO actual;
    IF actual IS DISTINCT FROM '1,2,4' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_top_products_by_category: top 3 Điện tử', '1,2,4', actual);
    END IF;

    EXECUTE 'select string_agg(column_name::text, '','' order by column_name) from information_schema.columns where table_schema = ''marts'' and table_name = ''mart_category_monthly_revenue'' and column_name <> ''category''' INTO actual;
    IF actual IS DISTINCT FROM '2026-07,2026-08,2026-09' THEN
        failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_category_monthly_revenue: cột tháng', '2026-07,2026-08,2026-09', actual);
    END IF;

    -- Compare all 9 pivot cells, including NULL versus zero; names alone are insufficient.
    IF EXISTS (
        WITH expected(category, jul, aug, sep) AS (
            VALUES ('Điện tử', 7500000.00::numeric, 84400000.00::numeric, 316300000.00::numeric),
                   ('Gia dụng', 650000.00::numeric, 3100000.00::numeric, NULL::numeric),
                   ('Thực phẩm', NULL::numeric, 450000.00::numeric, NULL::numeric)
        ), actual_pivot AS (
            SELECT category, "2026-07", "2026-08", "2026-09"
            FROM marts.mart_category_monthly_revenue
        )
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual_pivot)
        UNION ALL
        (SELECT * FROM actual_pivot EXCEPT ALL SELECT * FROM expected)
    ) THEN
        failures := failures || E'\n  - mart_category_monthly_revenue: sai ô pivot/NULL';
    END IF;

    IF failures <> '' THEN
        RAISE EXCEPTION 'Mart lệch so với kết quả kỳ vọng:%', failures;
    END IF;
    RAISE NOTICE 'Toàn bộ % kiểm tra golden đều khớp', 15;
END
$$;

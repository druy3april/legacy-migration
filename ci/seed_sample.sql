-- Dữ liệu mẫu nhỏ, cố định (deterministic) cho CI: nạp thẳng vào raw.* trên Postgres.
-- Không cần SQL Server/MinIO. Chạy SAU warehouse/init.sql.
-- 200 khách (10 khách không có đơn), 24 sản phẩm / 4 danh mục, 1.500 đơn, 1-3 dòng/đơn.
-- Khách 1-12 mua đồ điện tử (=> VIP), 13-30 mua laptop ít hơn (=> REGULAR), còn lại mua phụ kiện/gia dụng.
BEGIN;

TRUNCATE raw.order_items, raw.orders, raw.products, raw.customers;

INSERT INTO raw.customers (customer_id, full_name, email, city, created_at, row_ver)
SELECT i,
       'Khach hang ' || i,
       'kh' || i || '@example.com',
       CASE WHEN i % 10 = 0 THEN NULL
            ELSE (ARRAY['Ha Noi', 'TP HCM', 'Da Nang', 'Can Tho'])[1 + i % 4] END,
       timestamp '2026-01-01' + (i || ' hours')::interval,
       i
FROM generate_series(1, 200) AS i;

INSERT INTO raw.products (product_id, product_name, category, unit_price, is_active, created_at, row_ver)
SELECT i,
       'San pham ' || i,
       (ARRAY['Dien thoai', 'Laptop', 'Phu kien', 'Gia dung'])[1 + (i - 1) / 6],
       CASE WHEN i <= 6  THEN (5 + (i * 7) % 15) * 1000000      -- Dien thoai: 5-19 trieu
            WHEN i <= 12 THEN (10 + (i * 7) % 20) * 1000000     -- Laptop: 10-29 trieu
            WHEN i <= 18 THEN (200 + (i * 37) % 800) * 1000     -- Phu kien: 0,2-1 trieu
            ELSE (500 + (i * 53) % 2500) * 1000 END,            -- Gia dung: 0,5-3 trieu
       i % 20 <> 0,
       timestamp '2026-01-01',
       1000 + i
FROM generate_series(1, 24) AS i;

-- Khách 191-200 không có đơn nào => segment INACTIVE
INSERT INTO raw.orders (order_id, customer_id, order_date, status, total_amount, updated_at, row_ver)
SELECT i,
       1 + (i * 7) % 190,
       timestamp '2026-04-01' + ((i * 13) % 180 || ' days')::interval + ((i * 3607) % 86400 || ' seconds')::interval,
       CASE WHEN i % 20 < 12 THEN 'COMPLETED'
            WHEN i % 20 < 14 THEN 'SHIPPED'
            WHEN i % 20 < 16 THEN 'PAID'
            WHEN i % 20 = 16 THEN 'NEW'
            ELSE 'CANCELLED' END,
       0,
       timestamp '2026-04-02' + ((i * 13) % 180 || ' days')::interval,
       10000 + i
FROM generate_series(1, 1500) AS i;

INSERT INTO raw.order_items (order_item_id, order_id, product_id, quantity, unit_price, row_ver)
SELECT row_number() OVER (ORDER BY o.order_id, n),
       o.order_id,
       pick.product_id,
       CASE WHEN o.customer_id <= 30 THEN 1 ELSE 1 + (o.order_id + n) % 4 END,
       p.unit_price,
       20000 + row_number() OVER (ORDER BY o.order_id, n)
FROM raw.orders AS o
CROSS JOIN LATERAL generate_series(1, 1 + o.order_id % 3) AS n
CROSS JOIN LATERAL (
    SELECT CASE WHEN o.customer_id <= 12 THEN 1 + (o.order_id * 5 + n * 11) % 12
                WHEN o.customer_id <= 30 AND n = 1 THEN 7 + o.order_id % 6
                ELSE 13 + (o.order_id * 5 + n * 11) % 12 END AS product_id
) AS pick
JOIN raw.products AS p ON p.product_id = pick.product_id;

UPDATE raw.orders AS o
SET total_amount = t.total
FROM (SELECT order_id, sum(quantity * unit_price) AS total
      FROM raw.order_items GROUP BY order_id) AS t
WHERE t.order_id = o.order_id;

-- Một dòng bị xóa cứng ở nguồn (tombstone) để kiểm tra staging lọc _deleted_at
UPDATE raw.order_items SET _deleted_at = now() WHERE order_item_id = 1;

-- Freshness đo trên etl.ingest_log (xem lessons_learned mục 6)
INSERT INTO etl.ingest_log (run_id, table_name, from_rowversion, to_rowversion, row_count, object_key)
SELECT 'ci_seed', t, 0, 0, 0, NULL
FROM unnest(ARRAY['customers', 'products', 'orders', 'order_items']) AS t;

COMMIT;

SELECT 'customers' AS tbl, count(*) FROM raw.customers
UNION ALL SELECT 'products', count(*) FROM raw.products
UNION ALL SELECT 'orders', count(*) FROM raw.orders
UNION ALL SELECT 'order_items', count(*) FROM raw.order_items;
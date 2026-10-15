-- Dữ liệu mẫu nhỏ cho CI: nạp thẳng vào raw.* sau khi chạy warehouse/init.sql.
-- Mục đích: dbt build chạy được trên GitHub Actions mà không cần SQL Server/MinIO.
-- Bộ dữ liệu cố ý chứa các trường hợp biên: khách chưa mua, khách chỉ có đơn NEW/CANCELLED,
-- khách DORMANT, ngày trống giữa các đơn (date spine), danh mục > 3 sản phẩm (top 3),
-- sản phẩm chưa bán, dòng đã bị xóa ở nguồn (_deleted_at). Kết quả kỳ vọng: ci/assert_expected_marts.sql
-- File được sinh một lần rồi commit; sửa dữ liệu thì phải sửa cả file kỳ vọng.

BEGIN;

TRUNCATE raw.customers, raw.products, raw.orders, raw.order_items;
TRUNCATE etl.ingest_log;

INSERT INTO raw.customers (customer_id, full_name, email, city, created_at, row_ver, _deleted_at) VALUES
    (1, 'Nguyễn Văn An', 'an.nguyen@example.com', 'Hà Nội', '2026-06-01 08:00:00', 1001, NULL),
    (2, 'Trần Thị Bình', 'binh.tran@example.com', 'TP. Hồ Chí Minh', '2026-06-01 08:00:00', 1002, NULL),
    (3, 'Lê Văn Cường', 'cuong.le@example.com', 'Đà Nẵng', '2026-06-01 08:00:00', 1003, NULL),
    (4, 'Phạm Thị Dung', 'dung.pham@example.com', NULL, '2026-06-01 08:00:00', 1004, NULL),
    (5, 'Hoàng Văn Em', 'em.hoang@example.com', 'Huế', '2026-06-01 08:00:00', 1005, NULL),
    (6, 'Vũ Thị Giang', 'giang.vu@example.com', 'Cần Thơ', '2026-06-01 08:00:00', 1006, NULL),
    (7, 'Đặng Văn Hải', 'hai.dang@example.com', 'Hải Phòng', '2026-06-01 08:00:00', 1007, NULL),
    (8, 'Bùi Thị Hoa', 'hoa.bui@example.com', 'Nha Trang', '2026-06-01 08:00:00', 1008, '2026-09-25 01:00:00+00');

INSERT INTO raw.products (product_id, product_name, category, unit_price, is_active, created_at, row_ver) VALUES
    (1, 'Điện thoại Loại 1', 'Điện tử', 12000000.00, true, '2026-06-01 08:00:00', 1009),
    (2, 'Máy tính bảng Loại 1', 'Điện tử', 9500000.00, true, '2026-06-01 08:00:00', 1010),
    (3, 'Tai nghe Loại 2', 'Điện tử', 1200000.00, true, '2026-06-01 08:00:00', 1011),
    (4, 'Loa bluetooth Loại 1', 'Điện tử', 2500000.00, true, '2026-06-01 08:00:00', 1012),
    (5, 'Nồi cơm điện Loại 1', 'Gia dụng', 1800000.00, true, '2026-06-01 08:00:00', 1013),
    (6, 'Quạt điện Loại 3', 'Gia dụng', 650000.00, true, '2026-06-01 08:00:00', 1014),
    (7, 'Cà phê Loại 1', 'Thực phẩm', 150000.00, true, '2026-06-01 08:00:00', 1015),
    (8, 'Trà Loại 2', 'Thực phẩm', 90000.00, true, '2026-06-01 08:00:00', 1016);

INSERT INTO raw.orders (order_id, customer_id, order_date, status, total_amount, updated_at, row_ver, _deleted_at) VALUES
    (1, 1, '2026-09-01 09:15:00', 'COMPLETED', 167500000.00, '2026-09-01 09:15:00', 1017, NULL),
    (2, 1, '2026-09-20 14:30:00', 'SHIPPED', 96000000.00, '2026-09-20 14:30:00', 1020, NULL),
    (3, 2, '2026-08-10 10:00:00', 'COMPLETED', 82000000.00, '2026-08-10 10:00:00', 1022, NULL),
    (4, 2, '2026-09-15 16:45:00', 'PAID', 48000000.00, '2026-09-15 16:45:00', 1025, NULL),
    (5, 2, '2026-09-28 20:00:00', 'CANCELLED', 24000000.00, '2026-09-28 20:00:00', 1027, NULL),
    (6, 3, '2026-08-10 11:20:00', 'COMPLETED', 2850000.00, '2026-08-10 11:20:00', 1029, NULL),
    (7, 3, '2026-09-20 08:05:00', 'NEW', 1800000.00, '2026-09-20 08:05:00', 1032, NULL),
    (8, 4, '2026-07-15 19:00:00', 'COMPLETED', 8150000.00, '2026-07-15 19:00:00', 1034, NULL),
    (9, 5, '2026-08-12 13:00:00', 'CANCELLED', 12000000.00, '2026-08-12 13:00:00', 1037, NULL),
    (10, 5, '2026-09-01 07:30:00', 'NEW', 300000.00, '2026-09-01 07:30:00', 1039, NULL),
    (11, 6, '2026-08-12 15:10:00', 'SHIPPED', 3100000.00, '2026-08-12 15:10:00', 1041, NULL),
    (12, 6, '2026-09-15 09:40:00', 'COMPLETED', 4800000.00, '2026-09-15 09:40:00', 1044, NULL),
    (13, 6, '2026-09-15 10:00:00', 'COMPLETED', 0.00, '2026-09-15 10:00:00', 1047, '2026-09-25 01:00:00+00');

INSERT INTO raw.order_items (order_item_id, order_id, product_id, quantity, unit_price, row_ver, _deleted_at) VALUES
    (1, 1, 1, 10, 12000000.00, 1018, NULL),
    (2, 1, 2, 5, 9500000.00, 1019, NULL),
    (3, 2, 1, 8, 12000000.00, 1021, NULL),
    (4, 3, 2, 6, 9500000.00, 1023, NULL),
    (5, 3, 4, 10, 2500000.00, 1024, NULL),
    (6, 4, 1, 4, 12000000.00, 1026, NULL),
    (7, 5, 1, 2, 12000000.00, 1028, NULL),
    (8, 6, 3, 2, 1200000.00, 1030, NULL),
    (9, 6, 7, 3, 150000.00, 1031, NULL),
    (10, 7, 5, 1, 1800000.00, 1033, NULL),
    (11, 8, 4, 3, 2500000.00, 1035, NULL),
    (12, 8, 6, 1, 650000.00, 1036, NULL),
    (13, 9, 1, 1, 12000000.00, 1038, NULL),
    (14, 10, 7, 2, 150000.00, 1040, NULL),
    (15, 11, 5, 1, 1800000.00, 1042, NULL),
    (16, 11, 6, 2, 650000.00, 1043, NULL),
    (17, 12, 3, 4, 1200000.00, 1045, NULL),
    (18, 12, 7, 1, 150000.00, 1046, '2026-09-25 01:00:00+00'),
    (19, 13, 2, 1, 9500000.00, 1048, '2026-09-25 01:00:00+00');

-- Mỗi bảng một dòng log để dbt source freshness có mốc thời gian mới
INSERT INTO etl.ingest_log (run_id, table_name, from_rowversion, to_rowversion, row_count, object_key) VALUES
    ('ci-sample', 'customers', 0, 1048, 8, NULL),
    ('ci-sample', 'products', 0, 1048, 8, NULL),
    ('ci-sample', 'orders', 0, 1048, 13, NULL),
    ('ci-sample', 'order_items', 0, 1048, 19, NULL);

UPDATE etl.watermarks SET last_rowversion = 1048, last_run_at = now();

COMMIT;

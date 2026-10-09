# Tuần 2 — Bằng chứng kiểm thử ingestion

Các run dưới đây được chạy trên Docker Compose local ngày 2026-10-08 và
2026-10-09. Số liệu lấy trực tiếp từ `etl.ingest_log`, raw Postgres và
`task_instance` của Airflow.

## Kịch bản đã chạy

| Kịch bản | Run ID | Kết quả quan sát |
|---|---|---|
| Tải đầy đủ ban đầu | `evidence-01-full-load` | customers 2.009, products 60, orders 20.000, order_items 60.209 |
| Chạy lại không đổi | `evidence-02-no-change` | Cả bốn bảng ghi 0 dòng |
| Chỉ thay đổi đơn hàng | `evidence-03-order-changes` | customers 0, products 0, orders 15, order_items 13; 10 đơn đổi trạng thái và 5 đơn mới |
| Clear task trong cùng run | `evidence-04b-clear-replay` | Các task mapped `ingest` chạy lần 2 (`try_number=2`); cả hai lượt đều ghi 0 dòng |
| MinIO tạm dừng rồi phục hồi | `evidence-05-minio-retry` | Mapped task cần MinIO thành công ở lần 2 (`try_number=2`); orders 1, order_items 2 |
| Lệch schema nguồn | `evidence-06-schema-drift` | `ingest` của customers failed lần 1 với thông báo cột `phone`; ba bảng khác success |
| Xóa cứng trước khi có tombstone | `evidence-07-hard-delete` | orders 2, order_items 0; raw còn hai item đã bị xóa ở nguồn |
| Dò các xóa cũ | `evidence-26-detect-existing-deletes` | Dò và đánh dấu hai dòng order_items bị xóa ở kịch bản trước |
| Xác minh phát hiện xóa | `evidence-26b-detect-new-deletes` | Sau khi xóa thêm hai item, orders 2; raw giữ nguyên 60.224 dòng order_items và tổng cộng 4 dòng được đánh dấu `_deleted_at` |
| DAG sau khi thêm guard nguồn rỗng | `evidence-12-empty-source-guard` | Cả bốn task ingest, task detect_deletes và summarize thành công với nguồn có khóa |

Sau kịch bản schema drift, cột thử nghiệm `dbo.customers.phone` đã được xóa.
Sau khi triển khai delete detection, chạy lại detector không đánh dấu thêm
dòng nào (0 dòng mới), xác nhận các tombstone được giữ idempotent.
Unit test của guard xác nhận tỷ lệ xóa vượt `MAX_DELETE_RATIO` sẽ ném
`DeleteGuardError`; tỷ lệ xóa hợp lệ 3/59.911 được cho phép. DAG chuyển lỗi này
thành `AirflowFailException` để không retry vô ích.

## Trạng thái dữ liệu tại thời điểm kiểm tra

| Bảng | Nguồn SQL Server | Raw Postgres | `_deleted_at IS NOT NULL` |
|---|---:|---:|---:|
| customers | 2.009 | 2.009 | 0 |
| products | 60 | 60 | 0 |
| orders | 20.006 | 20.006 | 0 |
| order_items | 60.220 | 60.224 | 4 |

Ảnh chụp giao diện Airflow đã được xem trong phiên làm việc nhưng chưa được
lưu thành tệp trong repository. Run ID ở trên có thể dùng để tra lại log nếu
metadata database Airflow local còn được giữ.

## Truy vấn tái kiểm tra

```sql
SELECT run_id, table_name, row_count, from_rowversion, to_rowversion
FROM etl.ingest_log
ORDER BY id DESC
LIMIT 12;

SELECT 'customers' AS table_name, COUNT(*) AS raw_count FROM raw.customers
UNION ALL SELECT 'orders', COUNT(*) FROM raw.orders
UNION ALL SELECT 'order_items', COUNT(*) FROM raw.order_items;

SELECT COUNT(*) AS marked_deleted
FROM raw.order_items
WHERE _deleted_at IS NOT NULL;
```

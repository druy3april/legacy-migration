# ADR-0006: Chọn dbt Core cho tầng biến đổi

- Trạng thái: Đã chấp nhận
- Ngày: 2026-10-11

## Bối cảnh

Logic báo cáo nằm trong 7 stored procedure T-SQL: không có test, không có lịch
sử thay đổi, không thấy được bảng nào phụ thuộc bảng nào, và một số procedure
dùng SQL động. Hệ thống mới cần viết lại logic này trên PostgreSQL, chứng minh
được kết quả đúng, và sau này có thể chuyển sang warehouse trên cloud.

## Các phương án

| Phương án | Ưu | Nhược |
|---|---|---|
| Viết lại thành hàm/procedure PL/pgSQL | Gần cách làm cũ, đội SQL Server quen | Lặp lại đúng các vấn đề cũ: khó test, khó review, gắn chặt vào một engine |
| Python (pandas) trong task Airflow | Linh hoạt, dễ unit test hàm | Kéo dữ liệu ra khỏi warehouse; logic SQL bị phân tán trong code Python; khó mở rộng khi dữ liệu lớn |
| SQL trong operator của Airflow | Ít công cụ mới | Không có quản lý phụ thuộc, test dữ liệu hay tài liệu lineage |
| dbt Core | Mỗi bảng một file SQL có version; `ref()` tự sinh thứ tự chạy và lineage; test dữ liệu khai báo bằng YAML; Jinja thay cho SQL động; chạy trên nhiều warehouse | Thêm một công cụ và Jinja cần học; logic động (pivot) phải dùng `run_query` lúc biên dịch |

## Quyết định

Dùng dbt Core với adapter `dbt-postgres`, tổ chức ba tầng `staging` (làm sạch,
lọc dòng đã xóa), `intermediate` (dạng dọc ổn định) và `marts` (bảng báo cáo thay
cho từng procedure).

- Mỗi procedure có ít nhất một model tương ứng và được ghi lại cách chuyển trong
  [migration_notes.md](../migration_notes.md).
- Test bắt buộc: `unique`/`not_null` cho khóa, `relationships`, `accepted_values`,
  test tùy biến không âm, không giảm dòng bất thường, và `source freshness`.
- dbt được cài trong venv riêng trong image Airflow để không xung đột thư viện,
  và chạy qua DAG `transform_dbt` khi Asset `warehouse_raw` được cập nhật.
- Test của dbt chỉ chứng minh dữ liệu thỏa ràng buộc; việc khớp số liệu với hệ
  thống cũ do module đối soát đảm nhiệm ([ADR-0004](./0004-nguong-sai-so-va-snapshot-doi-soat.md)).

## Hệ quả

- Thay đổi logic đi qua pull request; CI chạy `dbt build` trên dữ liệu mẫu và so
  con số với kết quả kỳ vọng trước khi merge.
- Lineage và tài liệu sinh tự động bằng `dbt docs generate`.
- Chuyển sang warehouse khác chủ yếu là đổi adapter; vài chỗ dùng cú pháp riêng
  của PostgreSQL phải sửa (liệt kê trong [architecture.md](../architecture.md),
  mục 7).
- Model có pivot động phụ thuộc dữ liệu lúc biên dịch; đã thêm điều kiện để
  `dbt compile` chạy được trên database mới ([lessons_learned.md](../lessons_learned.md), mục 10).

## Theo dõi build

CLI và Airflow chạy qua `reconciliation.build`: giữ khóa ghi raw của pipeline,
kiểm tra freshness từng bảng, ghi batch đầu vào và invocation ID. Chỉ build đủ
model/test mới PASS; build một phần phục vụ debug trả mã 2 và không dùng cutover.

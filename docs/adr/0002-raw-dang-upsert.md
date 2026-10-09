# ADR-0002: Raw dùng upsert thay vì append

- Trạng thái: Đã chấp nhận
- Ngày: 2026-10-09

## Quyết định

Raw biểu diễn trạng thái hiện tại của từng khóa nguồn nên dùng upsert: khóa mới
được thêm, khóa đã có chỉ được cập nhật khi `row_ver` mới hơn. Chạy lại một
batch không tạo bản sao và không ghi đè phiên bản mới bằng dữ liệu cũ. Khi một
bản ghi có khóa đó xuất hiện lại trong nguồn, upsert xóa `_deleted_at` để đánh
dấu bản ghi là hiện hành.

Lịch sử các batch được lưu thành file Parquet bất biến trên MinIO và được tham
chiếu trong `etl.ingest_log`; bảng raw không phải kho lịch sử phiên bản.

## Tải lại (backfill)

- Ưu tiên phát lại file Parquet đã lưu trên MinIO bằng loader tương ứng với schema
  đích; kiểm tra `row_ver` trước khi upsert.
- Nếu cần trích xuất lại từ nguồn, hạ `etl.watermarks.last_rowversion` cho bảng
  cần nạp rồi chạy incremental. Cách này chỉ lấy các dòng còn tồn tại ở nguồn;
  nó không khôi phục được dòng đã DELETE. Việc xử lý DELETE thuộc ADR-0001.
- Hạ watermark có thể tạo lại batch cùng khoảng `rowversion`; raw upsert vẫn
  chống trùng, nhưng `etl.ingest_log` sẽ ghi thêm lịch sử lần chạy lại.

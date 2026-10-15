# ADR-0002: Raw upsert và snapshot bất biến để phục hồi

- Trạng thái: Đã chấp nhận cho lab
- Cập nhật: 2026-10-14

## Quyết định

Raw giữ trạng thái hiện tại bằng upsert theo khóa và rowversion; staging lọc
`_deleted_at IS NULL`. Đây là khác biệt có chủ đích so với đề xuất raw append
trong hướng dẫn gốc. Không cần viết lại 12 model chỉ để đổi cách lưu raw.

Incremental dùng key `raw/<bảng>/incremental/rv_<from>_<to>_<sha256>.parquet`.
Ghi object với `IfNoneMatch="*"`; retry chỉ chấp nhận object có nội dung giống
hệt. Cùng khoảng watermark nhưng bytes khác phải thành key khác, không ghi đè.

Sau khi đủ bốn bảng và source/raw khớp, lưu snapshot đầy đủ của raw, bao gồm
`_loaded_at`, `_deleted_at`, theo key nội dung và một manifest có SHA-256.
`etl.ingest_batches.manifest_key` trỏ tới manifest. Snapshot đã phát hành không
bị thay đổi bởi code này; tài khoản quản trị vẫn có quyền xóa object. Production
cần thêm versioning/Object Lock, retention và sao lưu khác tài khoản.

## Phục hồi

`make restore-raw MANIFEST=manifests/<sha256>.json RESTORE_DB=restore_lab`
khôi phục vào database mới, kiểm tra hash file, schema, số dòng, dữ liệu active
và toàn bộ tombstone. Chạy lại cùng manifest không nhân bản. Snapshot khác phải
vào database khác. Watermark của pipeline đang chạy không bị thay đổi.

Phục hồi snapshot khác với tải lại nguồn hiện tại: hạ watermark không tạo được
lịch sử đã mất ở SQL Server. Khi nối nguồn vào database phục hồi cần quy trình
rebaseline riêng; không dùng bộ đếm rowversion giữa hai database SQL Server.

## Đánh đổi

Mỗi batch lưu full snapshot phù hợp lab ~83 nghìn dòng; lịch sử tốn dung lượng.
Quy mô lớn chuyển CDC/Change Tracking + lịch sử thay đổi và checkpoint định kỳ.

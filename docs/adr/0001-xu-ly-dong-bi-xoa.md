# ADR-0001: Xử lý dòng bị xóa ở nguồn

- Trạng thái: Đã chấp nhận
- Ngày: 2026-10-09

## Bối cảnh

SQL Server `rowversion` thay đổi khi dòng được INSERT hoặc UPDATE. Khi dòng bị
DELETE, nó biến mất khỏi nguồn và không có `rowversion` mới để luồng incremental
phát hiện. Vì vậy bản ghi tương ứng vẫn nằm trong raw và có thể bị tính thừa ở
các báo cáo. Ví dụ: `order_items` bị xóa khi khách bỏ bớt món hàng.

## Các phương án

| Phương án | Ưu | Nhược |
|---|---|---|
| Soft delete ở nguồn (`is_deleted`) | Đơn giản nhất cho phía tải | Cần sửa ứng dụng cũ, thường không được phép trong dự án di chuyển |
| So sánh tập khóa hằng đêm | Không sửa nguồn; dễ hiểu và dễ kiểm thử | Quét toàn bộ khóa mỗi lần chạy; phát hiện xóa trễ tối đa một chu kỳ chạy |
| Change Tracking | SQL Server ghi nhận khóa của dòng bị xóa với chi phí thấp | Cần DBA bật trên database; có thời hạn lưu, quá hạn phải đồng bộ lại |
| CDC | Có cả giá trị trước/sau khi thay đổi | Cần SQL Server Agent, tốn tài nguyên và phức tạp hơn |

## Quyết định

Chọn so sánh tập khóa. Đây là phương án không yêu cầu thay đổi hệ thống nguồn,
đồng thời phù hợp với dữ liệu hiện tại ở quy mô vài chục nghìn dòng mỗi bảng.
Sau mỗi lần nạp incremental, task `detect_deletes` đọc tập khóa chính hiện có ở
nguồn, so với raw và đánh dấu các dòng không còn trong nguồn bằng `_deleted_at`.
Raw không xóa vật lý các dòng này để giữ dấu vết phục vụ kiểm tra.

Chuyển sang Change Tracking khi một bảng vượt khoảng 1.000.000 khóa hoặc việc
quét khóa toàn bảng mất trên 5 phút trong cửa sổ nạp đêm, sau khi DBA duyệt cấu
hình retention và có quy trình phát hiện watermark đã quá hạn.

## Hệ quả

- Bốn bảng raw có cột `_deleted_at TIMESTAMPTZ`; schema được nâng cấp an toàn
  bằng `ADD COLUMN IF NOT EXISTS`.
- Dòng bị xóa vẫn được giữ trong raw. Các mô hình staging tuần 3 trở đi phải lọc
  `WHERE _deleted_at IS NULL` khi biểu diễn trạng thái hiện hành.
- Phát hiện xóa chạy sau khi nạp mỗi bảng. Việc đánh dấu không thay đổi
  `rowversion` watermark; mỗi lần quét chỉ đánh dấu những dòng chưa có
  `_deleted_at`.
- `rowversion` không ghi nhận DELETE; độ trễ phát hiện tối đa là một chu kỳ chạy.
- Tập khóa được truyền theo lô vào bảng tạm Postgres, không cần giữ toàn bộ khóa
  của bảng trong bộ nhớ Python.
- Trước khi đánh dấu, detector chặn nếu tỷ lệ dòng raw đang hoạt động dự kiến bị
  đánh dấu xóa vượt `MAX_DELETE_RATIO` (mặc định `0.05`). Chỉ tăng ngưỡng có chủ
  ý sau khi xác minh nguồn nếu một đợt xóa hợp lệ lớn hơn ngưỡng.

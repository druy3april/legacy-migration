# ADR-0005: Bắt thay đổi ở nguồn bằng watermark `rowversion`

- Trạng thái: Đã chấp nhận
- Ngày: 2026-10-11

## Bối cảnh

Ingestion phải chỉ tải các dòng mới hoặc vừa sửa trong SQL Server, không bỏ sót
dòng nào và chạy lại được nhiều lần mà không tạo trùng. Hệ thống cũ là ứng dụng
đang vận hành: không được sửa code ứng dụng, và mọi thay đổi cấu hình database
phải qua DBA. Cả bốn bảng nguồn (`customers`, `products`, `orders`,
`order_items`) đã có sẵn cột `row_ver ROWVERSION`.

## Các phương án

| Phương án | Ưu | Nhược |
|---|---|---|
| Tải toàn bộ mỗi đêm | Đơn giản, tự bắt được cả dòng bị xóa | Thời gian và tải lên nguồn tăng tuyến tính theo dữ liệu; không phải incremental |
| Watermark theo `updated_at` | Dễ hiểu, phổ biến | Chỉ `orders` có `updated_at`, ba bảng còn lại không có; cột do ứng dụng tự ghi nên có thể quên cập nhật; hai dòng cùng mốc giờ dễ bị bỏ sót ở ranh giới |
| Watermark theo `rowversion` | Do SQL Server tự tăng ở mọi INSERT/UPDATE, không phụ thuộc ứng dụng; có sẵn ở cả 4 bảng; so sánh số nguyên chính xác | Không bắt được DELETE; là bộ đếm chung của cả database; transaction đang mở có thể giữ một giá trị nhỏ hơn giá trị đã thấy |
| Change Tracking | Bắt cả DELETE, chi phí thấp | Cần DBA bật; có thời hạn lưu, quá hạn phải đồng bộ lại toàn bộ |
| CDC | Có giá trị trước/sau khi đổi, đầy đủ nhất | Cần SQL Server Agent, tốn tài nguyên, vận hành phức tạp; vượt nhu cầu báo cáo |

## Quyết định

Dùng watermark `rowversion`, lưu ở `etl.watermarks.last_rowversion` dạng
`BIGINT` (`CAST(row_ver AS BIGINT)`).

- Cận trên an toàn của mỗi lần chạy là `MIN_ACTIVE_ROWVERSION() - 1`, không dùng
  `@@DBTS`, để không bỏ sót dòng của transaction đang mở
  ([lessons_learned.md](../lessons_learned.md), mục 1).
- Một lần chạy đọc cận trên **một lần** rồi dùng chung cho cả 4 bảng, để giới hạn
  khoảng tải; cách này không tạo snapshot transaction giữa bốn kết nối. Sau tải
  phải kiểm tra full fingerprint và chốt batch; không khớp thì chạy lại.
- Điều kiện tải: `row_ver > watermark_cũ AND row_ver <= cận_trên`. Watermark chỉ
  được cập nhật trong cùng transaction với lệnh nạp raw, nên lỗi giữa chừng không
  làm mất dữ liệu.
- Trước mỗi lần tải, so tên cột, kiểu, độ dài, precision/scale, nullable và datetime precision; khác nhau thì dừng với
  `SchemaDriftError` thay vì ghi sai.
- DELETE được xử lý riêng bằng so sánh tập khóa ([ADR-0001](./0001-xu-ly-dong-bi-xoa.md)).

## Hệ quả

- Không cần sửa ứng dụng hay xin quyền DBA để bật tính năng mới.
- File Parquet được định danh bằng SHA-256 và upsert không tạo
  trùng ([ADR-0002](./0002-raw-dang-upsert.md)).
- Khi dữ liệu lớn hoặc cần bắt DELETE ngay trong lần tải, chuyển sang Change
  Tracking theo ngưỡng đã ghi trong ADR-0001.
- Cột `rowversion` chỉ có ý nghĩa trong một database: nếu nguồn bị khôi phục từ
  backup hoặc chuyển server, phải tải lại toàn bộ và đặt lại watermark.

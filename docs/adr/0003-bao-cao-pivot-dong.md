# ADR-0003: Giữ báo cáo PIVOT động dạng dọc làm nguồn chính

- Trạng thái: Đã chấp nhận
- Ngày: 2026-10-09

## Bối cảnh

`dbo.sp_refresh_category_monthly_revenue` tạo cột động theo các tháng xuất hiện
trong đơn hàng. Schema của bảng đích vì vậy thay đổi khi có tháng mới. dbt cần
một model ổn định để downstream tham chiếu, kiểm thử và đối chiếu.

## Các phương án

| Phương án | Ưu | Nhược |
|---|---|---|
| Chỉ giữ dạng ngang/PIVOT động | Gần cấu trúc báo cáo SQL Server hiện tại | Số cột thay đổi theo dữ liệu; khó tham chiếu và test ổn định trong dbt |
| Chỉ giữ dạng dọc | Schema cố định; dễ lọc tháng, kiểm thử và làm phân tích tiếp | Người dùng quen báo cáo mỗi tháng một cột phải đổi cách đọc |
| Dạng dọc làm nguồn chính, dạng ngang làm mart tương thích | Có mô hình ổn định và vẫn giữ giao diện báo cáo cũ | Cần duy trì thêm một model pivot với cột động |

## Quyết định

Chọn phương án thứ ba. `int_category_monthly_revenue` là nguồn chuẩn ở dạng
dọc gồm `category`, `year_month`, `revenue`. `mart_category_monthly_revenue`
là lớp tương thích dạng ngang, sinh các cột tháng có trong orders tại lúc dbt
chạy.

Danh sách tháng lấy từ mọi order hiện hành, còn doanh thu chỉ tính các đơn
`PAID`, `SHIPPED`, `COMPLETED`, để khớp ý nghĩa procedure cũ. Do đó tháng chỉ
có đơn ngoài các status này có thể tồn tại như một cột với giá trị `NULL`.

## Hệ quả

- Downstream mới nên tham chiếu model dạng dọc để schema và test không phụ
  thuộc lịch chạy.
- Báo cáo cần mỗi tháng một cột có thể dùng mart ngang; cần chạy lại
  `dbt build` để cập nhật schema khi xuất hiện tháng mới.
- Khi đối soát, so cả tháng trong danh sách cột lẫn giá trị; không coi `NULL`
  của tháng không có doanh thu đủ điều kiện là doanh thu 0 nếu giao diện cần
  phân biệt hai trạng thái.
- Bằng chứng đối chiếu hiện tại nằm tại
  [`../evidence/dbt-sqlserver-reconciliation.md`](../evidence/dbt-sqlserver-reconciliation.md).

# Khôi phục dashboard Metabase

Metabase dùng database `metabase` riêng để lưu metadata ứng dụng. Sáu câu hỏi
và dashboard SQL Server ↔ dbt trong database đó cũng được lưu dưới dạng tài
nguyên trong repository:

- SQL câu hỏi Q1–Q6: [`questions/`](./questions/)
- Tên, kiểu biểu đồ, cấu hình biểu đồ và vị trí trên dashboard:
  [`dashboard.json`](./dashboard.json)

## Dựng lại

1. Dựng và khởi tạo PostgreSQL warehouse bằng `make wh`.
2. Khởi động Metabase bằng `make metabase`.
3. Trong Metabase, thêm một database PostgreSQL trỏ tới host `postgres`,
   port `5432`, database `warehouse`, schema `recon`, user `bi_reader`,
   password `bi_reader`.
4. Tạo sáu câu hỏi native SQL bằng nội dung các file Q1–Q6; đặt tiêu đề và
   visualization theo `dashboard.json`.
5. Tạo dashboard `Đối soát SQL Server ↔ dbt` rồi thêm các câu hỏi theo thứ tự
   và tọa độ row/col/width/height trong manifest.

`bi_reader` được tạo và chỉ được cấp quyền đọc trên schema `recon` và `marts`
trong [`warehouse/init.sql`](../warehouse/init.sql). Các file SQL dùng alias
cột tiếng Việt vì cấu hình biểu đồ hiện tại tham chiếu các tên đó.

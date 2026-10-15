# ADR-0004: Ngưỡng sai số và snapshot đối soát

- Trạng thái: Đã chấp nhận
- Ngày: 2026-10-11

## Bối cảnh

Đối soát SQL Server với dbt/Postgres so sánh các báo cáo được tạo bởi hai
engine khác nhau. Báo cáo cũ và mart mới có thể được tính tại hai thời điểm
khác nhau nếu nguồn thay đổi giữa ingestion và batch. Một số sai khác, như hòa
doanh thu ở ranh giới top 3, không có quy tắc phân hạng tương ứng trong
procedure cũ. Ngoài ra, ngày hiện được tính theo UTC; đổi sang giờ Việt Nam sẽ
thay đổi phân bổ ngày và có thể làm thay đổi báo cáo nghiệp vụ.

## Các phương án

| Phương án | Ưu | Nhược |
|---|---|---|
| (a) So tuyệt đối và chạy tay khi rảnh | Quy tắc đơn giản; sai khác nào cũng lộ rõ | Bất tiện với sai số biểu diễn; không bảo đảm cùng snapshot; đối soát không đều và hòa hạng dễ thành lỗi giả |
| (b) Ngưỡng sai số + snapshot fingerprint + `SKIP` | Tự động hóa được; chỉ kết luận khi cùng lát cắt nguồn; phân biệt sai khác chấp nhận được | Phải duy trì fingerprint và điều tra nếu `SKIP` kéo dài |
| (c) Đóng băng nguồn mỗi lần đối soát | Hai phía dùng cùng một snapshot dễ xác định | Cần dừng/khóa ghi ở hệ thống cũ; ảnh hưởng vận hành và không phù hợp chạy song song liên tục |

## Quyết định

Chọn phương án **(b)**.

- Tiền được chuẩn hóa về hai chữ số thập phân; chấp nhận độ lệch tuyệt đối
  không quá **0,01 VND**.
- So sánh theo năm cấp: số dòng/tập cột, aggregate, nhóm, từng khóa và
  checksum. Giá trị `NULL` không đồng nhất với 0.
- Kết quả có bốn trạng thái: `PASS` (khớp), `WARN` (chênh lệch được chấp nhận,
  như hòa hạng hoặc checksum khác trong ngưỡng L4), `SKIP` (snapshot không
  khớp hoặc chưa đủ điều kiện kết luận), `FAIL` (sai khác ngoài quy tắc chấp
  nhận).
- Hòa doanh thu tại ranh giới top 3 chỉ là `WARN` khi measure doanh thu bằng
  nhau và chỉ khác cột sản phẩm do procedure cũ không quy định tie-break.
- Fingerprint bốn bảng gồm số dòng, max rowversion và SHA-256 toàn bộ giá trị
  đã chuẩn hóa, sắp theo khóa. Batch cũ kiểm tra trước/sau; ingestion và dbt
  cùng ghi `ingest_run_id`. Đối soát kiểm tra lại fingerprint trước và sau.
- Chỉ build đầy đủ mới có trạng thái PASS. Build mới hơn bị lỗi hoặc PARTIAL
  chặn nghiệm thu; không dùng PASS cũ để thay thế.
- Một run phải đủ L0–L5 cho cả bảy báo cáo, tất cả PASS, cùng snapshot và không
  có dòng lệch mới đủ điều kiện cutover. Debug không ghi kết quả; SKIP trả lỗi.
- Đây là phép kiểm tra ổn định trong cửa sổ lab, không phải distributed snapshot.
  Đóng băng ghi lúc cutover. Nếu nguồn ghi liên tục, cần CDC/LSN hoặc snapshot
  transaction đồng bộ; hash trước/sau không tự tạo snapshot isolation.

## Hệ quả

- `SKIP` tránh ghi nhận sai khác giả do hai phía tính từ dữ liệu khác thời
  điểm; `SKIP` kéo dài vẫn là **sự cố vận hành**, cần khôi phục ingestion và
  đồng bộ snapshot thay vì bỏ qua điều kiện.
- Trạng thái chi tiết ở `recon.results`; trạng thái toàn run ở `recon.runs`.
  DAG chỉ xanh khi run đủ điều kiện; WARN vẫn phải điều tra, không tính ngày xanh.
- Quy tắc ngày UTC được giữ nguyên trong thời gian di chuyển. Đổi sang ngày giờ
  Việt Nam là **thay đổi nghiệp vụ** sau cutover, chỉ thực hiện khi nghiệp vụ
  duyệt; không sửa đồng thời với việc chuyển nền tảng (“làm đúng trước”, quy
  tắc 4).
- Quy trình và kết quả kiểm chứng được ghi trong
  [`../reconciliation.md`](../reconciliation.md).

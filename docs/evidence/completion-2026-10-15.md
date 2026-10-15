# Nghiệm thu hiện trạng ngày 15/10/2026

Đây là kết quả kiểm tra trên bản triển khai local, sau khi đã áp dụng phụ lục.
Phụ lục B trong hướng dẫn là bản vá lịch sử để làm mục 5, không phải một bài tập
hay bước bổ sung. Không áp dụng lại vào source hiện tại đã sửa tiếp.

| Phần | Kết quả đã chứng minh |
|---|---|
| Nguồn và ingestion | 4 bảng; raw active khớp source theo fingerprint SHA-256 |
| dbt | 12 model, 49 test; freshness riêng 4 bảng; full build PASS |
| Đối soát | 7/7 PASS; 87 checks; 0 dòng lệch; run eligible |
| BI | 14 question chạy bằng tài khoản BI; dashboard OLD/NEW mỗi bên 7; định nghĩa đã xuất vào repo |
| Q4 | Đã sửa bản lưu trong Metabase dùng recon.v_green_streak; hiện 1 ngày |
| Phục hồi | Snapshot thật restore vào restore_rehearsal_20261014, chạy lại hai lần RESTORE PASS |
| CI local | 44 test Python/SQL, 15 golden assertions, Ruff/SQLFluff/dbt đều PASS |
| Terraform | fmt/validate/plan PASS; 13 add, 0 change, 0 destroy; không apply |
| Routing BI | Link cố định localhost:3001; diễn tập OLD → NEW → OLD qua HTTP 302 trên config tạm PASS |
| Quyền pivot | Giữ quyền đọc bi_legacy_reader sau DROP/CREATE, kể cả nguồn rỗng; có regression test |

## Bằng chứng

- `status-2026-10-15.json`: trạng thái DB/DAG, batch IDs, 14 SELECT, 7 so sánh.
- `cutover-rehearsal-2026-10-15.json`: routing HTTP thực, đo thời gian cấu hình;
  đây không phải RTO của người dùng và không phải phê duyệt Go.
- `storage-2026-10-15.json`: 58 object, 11.105.692 bytes tại thời điểm đo; 5 manifest.
- Log đầy đủ giữ local ở `artifacts/completion-20261015/`, backup ở `backups/`;
  hai thư mục không commit để tránh đưa dữ liệu riêng và log lớn lên repo.
- Dashboard OLD: http://localhost:3000/dashboard/3
- Dashboard NEW: http://localhost:3000/dashboard/4
- Link dùng cho chuyển nguồn: http://localhost:3001

## Còn phải đáp ứng trước khi tuyên bố hoàn tất

1. **Đủ 5 ngày lịch xanh thật:** hiện 1 ngày, ngày 15/10. Nếu liên tục thành công
   thì mốc sớm nhất là 19/10; không sửa timestamp để tạo ngày giả.
2. **CI trên chính commit bàn giao:** xem bằng chứng GitHub cập nhật kèm theo.
   PR cũ từng xanh không thay thế kiểm tra commit mới.
3. **Cutover thật sau Go:** lệnh `make cutover` chặn khi thiếu ngày hoặc snapshot
   không hợp lệ. Mọi diễn tập hiện tại chỉ dùng config tạm, link chung vẫn OLD.
4. **Chạy README trên máy/VM sạch và đo thời gian:** hiện đã kiểm tra database
   test cô lập và CI fresh checkout; không ghi nhận đã đạt 30 phút khi chưa đo.
5. Giai đoạn theo dõi 14 ngày sau cutover thuộc vận hành tiếp theo, chưa diễn ra.

## Lệnh vận hành

```bash
make audit          # đọc trạng thái, ghi evidence; không ghi vào database nghiệp vụ
make readiness      # exit 1 hiện là đúng: mới 1/5 ngày
make reports        # link cố định http://localhost:3001, khởi đầu trỏ OLD
make reports-status
make rehearse       # cấu hình và HTTP server tạm, không thay link chung
make cutover        # chỉ cho NEW khi đủ ngày + latest run và snapshot hợp lệ
make rollback       # quay OLD ngay, không cần database PostgreSQL còn hoạt động
```

Ruleset `bao-ve-main` hiện active, yêu cầu PR và hai check: Python và dbt.
Workflow giữ nguyên hai tên check đó; dbt phụ thuộc Terraform và luôn chạy bước
kiểm tra kết quả Terraform, nên Terraform lỗi/cancel không bị bỏ qua như một
job skipped được GitHub coi là thành công.

# Kế hoạch cutover và rollback

> Trạng thái 15/10/2026: đã diễn tập HTTP routing OLD → NEW → OLD trên cấu hình
> tạm; chưa Go cho cutover thật vì mới 1/5 ngày xanh. Xem evidence/completion-2026-10-15.md.
> Sau khi triển khai bản vá, đối chiếu quy trình chi tiết trong
> `HUONG_DAN_HOAN_THIEN_DAY_DU.md`, mục cutover và rollback.

Mục tiêu: chuyển 7 báo cáo từ job ban đêm trên SQL Server sang pipeline Airflow
+ dbt mà người dùng báo cáo không thấy số liệu sai, và quay lại được hệ thống cũ
trong vài phút nếu có sự cố.

## 1. Phạm vi

| Báo cáo cũ (SQL Server) | Báo cáo mới (PostgreSQL) | Procedure bị thay |
|---|---|---|
| `dbo.daily_revenue` | `marts.mart_daily_revenue` | `sp_refresh_daily_revenue` |
| `dbo.customer_ltv` | `marts.mart_customer_ltv` | `sp_refresh_customer_ltv` |
| `dbo.customer_segments` | `marts.mart_customer_segments` | `sp_refresh_customer_segments` |
| `dbo.product_sales` | `marts.mart_product_sales` | `sp_refresh_product_sales` |
| `dbo.category_monthly_revenue` | `marts.mart_category_monthly_revenue` | `sp_refresh_category_monthly_revenue` |
| `dbo.cumulative_revenue` | `marts.mart_cumulative_revenue` | `sp_refresh_cumulative_revenue` |
| `dbo.top_products_by_category` | `marts.mart_top_products_by_category` | `sp_refresh_top_products_by_category` |

Không thuộc phạm vi: ứng dụng bán hàng và các bảng nguồn trên SQL Server (vẫn
giữ nguyên, tiếp tục là nguồn dữ liệu).

## 2. Người liên quan và kênh liên lạc

| Vai trò | Trách nhiệm | Quyết định |
|---|---|---|
| Data engineer (người thực hiện) | Chạy các bước, theo dõi DAG, đối soát, thực hiện rollback | Đề xuất Go/No-Go, kích hoạt rollback khi chạm điều kiện |
| Chủ sở hữu nghiệp vụ báo cáo (tài chính/kinh doanh) | Kiểm tra số trên dashboard sau khi chuyển | **Duyệt Go/No-Go**, xác nhận số đúng |
| DBA SQL Server | Sao lưu, tắt/bật lại job ban đêm cũ | Duyệt thay đổi trên SQL Server |
| Người dùng báo cáo | Nhận thông báo, báo lỗi số liệu | — |

| Kênh | Dùng cho |
|---|---|
| Nhóm chat dự án (ví dụ `#data-migration`) | Cập nhật từng bước trong đêm cutover và giai đoạn theo dõi |
| Email tới người dùng báo cáo | Thông báo trước (T-3), xác nhận hoàn tất (T0), thông báo rollback nếu có |
| Email cảnh báo của Airflow (`ALERT_EMAIL_TO`) | Lỗi DAG, FAIL đối soát |

## 3. Điều kiện để được chuyển (Go/No-Go)

Tất cả phải đúng tại thời điểm họp Go/No-Go (T-1):

| # | Điều kiện | Cách kiểm tra |
|---|---|---|
| 1 | Đủ **5 ngày đối soát xanh liên tiếp**: mỗi ngày một run hoàn chỉnh, đủ 7 báo cáo, tất cả PASS, 0 dòng lệch, không bỏ trống ngày nào | `make readiness` trả exit code 0; Q4 trên dashboard ≥ 5 |
| 2 | Không có `SKIP` kéo dài hay `WARN` chưa được duyệt trong 5 ngày đó | Q2 trên dashboard |
| 3 | `dbt build` và `dbt source freshness` xanh ở lần chạy gần nhất | Airflow, DAG `transform_dbt` |
| 4 | CI xanh trên nhánh `main` | Tab Actions trên GitHub |
| 5 | Các chênh lệch có chủ đích đã được nghiệp vụ đồng ý | [reconciliation.md](./reconciliation.md), mục 6 |
| 6 | Đã có bản sao lưu ở bước T-1 | Mục 4 bên dưới |

Số ngày yêu cầu đặt bằng `CUTOVER_GREEN_DAYS` trong `.env`. Một ngày đỏ làm
chuỗi đếm lại từ 0.

## 4. Lịch trình

| Thời điểm | Việc | Người làm |
|---|---|---|
| T-7 | Đóng băng thay đổi: không sửa stored procedure, model dbt hay DAG trừ khi sửa lỗi chặn cutover | Data engineer |
| T-3 | Gửi thông báo cho người dùng: ngày chuyển, những gì thay đổi, ai cần liên hệ | Chủ sở hữu nghiệp vụ |
| T-1 | Họp Go/No-Go theo mục 3 | Tất cả |
| T-1 | Sao lưu: `BACKUP DATABASE LegacyRetail` trên SQL Server; `pg_dump` schema `marts`, `recon`, `raw`, `etl` trên PostgreSQL | DBA, data engineer |
| T0 | Thực hiện các bước ở mục 5 | Data engineer |
| T0 + 1 đến T0 + 14 | Giai đoạn theo dõi: hệ thống cũ vẫn chạy song song nhưng chỉ để đối chiếu; đối soát chạy mỗi đêm như trước | Data engineer |
| T0 + 14 | Họp đóng: nếu 14 ngày không có sự cố, tắt hẳn hệ thống báo cáo cũ (mục 7) | Tất cả |

## 5. Các bước trong ngày cutover (T0)

1. **Đóng băng nguồn trong lab:** tạm dừng DAG `simulate_source_activity`. Ở
   môi trường thật, thống nhất thời điểm cắt sau giờ giao dịch.
2. **Chạy lần cuối cả hai phía trên cùng một lát cắt:** trigger `ingest_legacy`.
   DAG `legacy_nightly_batch` và `transform_dbt` tự chạy, sau đó `reconciliation`
   tự chạy khi cả hai xong.
3. **Đối soát:** DAG `reconciliation` thành công, cả 7 báo cáo PASS, `diff_rows = 0`
   (Q5 trên dashboard). Bất kỳ FAIL hay SKIP nào: dừng, không chuyển, ghi lại
   lý do và hẹn lại.
4. **Trỏ link chung sang hệ thống mới:** người dùng mở http://localhost:3001.
   Chạy `make cutover` để chuyển từ dashboard OLD (3) sang NEW (4), sau khi guard
   xác nhận đủ ngày, latest run và snapshot. Giữ nguyên hai bộ question để rollback.
5. **Kiểm tra nhanh:** chủ sở hữu nghiệp vụ mở 3 báo cáo quan trọng nhất (doanh
   thu ngày, phân khúc khách hàng, top sản phẩm) và so với kết quả SQL Server trong cùng lần chốt cuối cùng.
6. **Bật lại nguồn:** bật lại `simulate_source_activity` (lab) hoặc mở lại giao dịch.
7. **Thông báo hoàn tất** qua email và nhóm chat, kèm cách báo lỗi.

## 6. Rollback

### Khi nào rollback

Kích hoạt rollback nếu xảy ra **một** trong các điều sau trong giai đoạn theo dõi:

| Điều kiện | Ví dụ |
|---|---|
| Đối soát FAIL mà không tìm ra và sửa được nguyên nhân trong 4 giờ làm việc | Một báo cáo lệch doanh thu theo ngày |
| `ingest_legacy` hoặc `transform_dbt` lỗi 2 đêm liên tiếp | Báo cáo sáng hôm sau bị cũ |
| `dbt source freshness` báo `error` (dữ liệu cũ hơn 50 giờ) | Ingestion ngừng chạy |
| Người dùng báo số sai và data engineer xác nhận lỗi nằm ở hệ thống mới | |

### Các bước rollback (trong giai đoạn theo dõi)

Vì hệ thống cũ vẫn chạy song song nên rollback chỉ là đổi nguồn báo cáo, mất
vài phút:

1. Báo trong nhóm chat: bắt đầu rollback, lý do.
2. Chạy `make rollback` để link chung quay về dashboard OLD. Không cần DB để đổi route.
3. Kiểm tra job ban đêm cũ (`sp_run_nightly_batch`) vẫn chạy và số liệu mới nhất.
4. Gửi email cho người dùng: đã quay về hệ thống cũ, số liệu nào cần xem lại.
5. Tìm nguyên nhân, sửa, ghi vào [lessons_learned.md](./lessons_learned.md).
6. Bắt đầu đếm lại 5 ngày xanh từ đầu rồi lên lịch cutover mới.

### Sau khi đã tắt hệ thống cũ

Sau T0 + 14, rollback nghĩa là bật lại SQL Server báo cáo, khôi phục bản sao lưu
và chạy lại `sp_run_nightly_batch`: mất vài giờ và cần DBA. Đây là lý do giữ hệ
thống cũ chạy song song đủ 14 ngày trước khi tắt.

## 7. Tắt hệ thống cũ (T0 + 14)

1. Tắt job ban đêm trên SQL Server (đổi tên hoặc disable job, chưa xóa procedure).
2. Chuyển các bảng `dbo.*` báo cáo sang chế độ chỉ đọc và giữ thêm 90 ngày để tra cứu.
3. Tạm dừng DAG `legacy_nightly_batch` và `reconciliation`. Đối soát với hệ thống
   cũ không còn ý nghĩa; chất lượng dữ liệu từ đây dựa vào test dbt, freshness
   và CI.
4. Cập nhật README và [architecture.md](./architecture.md): hệ thống cũ đã ngừng.

## 8. Mẫu thông báo

**T-3:**
> Từ ngày [T0], 7 báo cáo doanh thu và khách hàng sẽ lấy số từ nền tảng dữ liệu
> mới. Trong 5 ngày gần nhất, số liệu hai hệ thống khớp hoàn toàn. Giao diện báo
> cáo không đổi. Nếu thấy số bất thường, liên hệ [tên] qua [kênh].

**T0, hoàn tất:**
> Đã chuyển xong 7 báo cáo sang nền tảng mới lúc [giờ]. Đối soát lần cuối: 7/7
> khớp. Hệ thống cũ vẫn chạy song song 14 ngày để đối chiếu.

**Rollback:**
> Báo cáo [tên] đã được chuyển về hệ thống cũ lúc [giờ] do [lý do ngắn]. Số liệu
> hiện tại là số của hệ thống cũ. Chúng tôi sẽ thông báo lịch chuyển lại.

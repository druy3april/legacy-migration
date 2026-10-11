# Kế hoạch cutover và rollback

## 1. Phạm vi
- 7 báo cáo: daily_revenue, customer_ltv, customer_segments, product_sales,
  cumulative_revenue, top_products_by_category, category_monthly_revenue.
- Trước: người dùng đọc bảng dbo.* trên SQL Server (do sp_run_nightly_batch làm mới).
- Sau: người dùng đọc marts.* trên warehouse qua Metabase (user chỉ-đọc bi_reader).

## 2. Điều kiện GO (tất cả phải đạt)
| # | Điều kiện | Cách kiểm tra |
|---|---|---|
| 1 | ≥ 5 ngày đối soát xanh liên tiếp (7/7 PASS, diff_rows = 0, không SKIP) | `make readiness` → ready_for_cutover = t |
| 2 | dbt build + source freshness xanh trong lần chạy gần nhất | Airflow: transform_dbt success |
| 3 | CI xanh trên main | Tab Actions |
| 4 | Nghiệp vụ đã ký xác nhận các chênh lệch có chủ đích | reconciliation.md §6: hòa hạng top 3, ngày theo UTC, pivot NULL |
| 5 | Đã diễn tập rollback thành công trong vòng 7 ngày | docs/evidence/tuan6-dien-tap-cutover.md |
| 6 | Có bản sao lưu bảng báo cáo cũ và schema marts | mục 4, bước T0-3 |

## 3. Lịch trình
| Mốc | Việc | Người làm |
|---|---|---|
| T-7 | Thông báo lịch cutover và thời gian đóng băng | Data Engineer |
| T-3 | Diễn tập cutover + rollback trên môi trường thử | Data Engineer, BI |
| T-1 | Đóng băng thay đổi: không merge dbt/procedure, không đổi schema nguồn | Tất cả |
| T0 | Thực hiện mục 4 (khung giờ ít người dùng, ví dụ 06:00-08:00) | Data Engineer, BI |
| T+1 → T+14 | Giai đoạn theo dõi chặt (hypercare): batch cũ VẪN chạy song song, đối soát vẫn chạy hằng ngày | Data Engineer |
| T+14 | Nếu không có sự cố: tắt job cũ, lưu trữ bảng dbo.*, giữ bản sao lưu 90 ngày | DBA |

## 4. Các bước ngày T0
1. Xác nhận lại điều kiện GO (`make readiness`, Airflow, CI).
2. Chạy lần cuối cả hai hệ thống trên CÙNG snapshot: trigger `ingest_legacy`
   → `transform_dbt` + `legacy_nightly_batch` → `reconciliation` (tự chạy theo Asset).
3. Sao lưu: `pg_dump -n marts` + backup bảng dbo.* báo cáo trên SQL Server.
4. Đối soát lần cuối: 7/7 PASS. Ghi run_id vào biên bản.
5. Chuyển dashboard Metabase từ nguồn SQL Server sang marts.*.
6. Kiểm tra nhanh: 3 số liệu chốt (doanh thu hôm qua, tổng LTV, số khách VIP) khớp báo cáo cũ.
7. Thông báo go-live. Ghi giờ hoàn thành.

## 5. Điều kiện kích hoạt ROLLBACK
| Tình huống | Ngưỡng | Ai quyết định |
|---|---|---|
| Đối soát FAIL không giải thích được | > 4 giờ chưa tìm ra nguyên nhân | Data Engineer + chủ dữ liệu |
| Báo cáo không sẵn sàng | dbt build/freshness lỗi sau 08:00 | Data Engineer |
| Nghiệp vụ báo số sai và đã xác nhận | 1 lần | Chủ dữ liệu |
| Mất dữ liệu raw / guard xóa kích hoạt | bất kỳ | Data Engineer |

## 6. Các bước ROLLBACK (mục tiêu < 30 phút)
1. Chuyển dashboard Metabase về nguồn SQL Server (bảng dbo.* vẫn được làm mới nhờ batch cũ chạy song song).
2. Thông báo rollback (mẫu ở mục 8).
3. KHÔNG tắt pipeline mới: giữ chạy để điều tra; mở ticket nguyên nhân gốc.
4. Sửa → PR có CI xanh → chạy lại song song, **đếm lại N ngày từ 0**.

## 7. Người liên quan (RACI)
| Vai trò | Người | R/A/C/I | Kênh |
|---|---|---|---|
| Data Engineer (chủ trì) | bạn | R | |
| Chủ dữ liệu / Kế toán (ký xác nhận số) | | A | |
| BI / người làm dashboard | | R | |
| DBA SQL Server | | C | |
| Người dùng báo cáo | | I | |

## 8. Mẫu thông báo
- Đóng băng (T-1) · Go-live (T0) · Rollback.
````

### E.3 Diễn tập ở máy (bằng chứng cho "đã có kế hoạch rollback")

1. Metabase → **Admin → Databases → Add database → SQL Server**: host `sqlserver`, port `1433`, database `LegacyRetail`, user `sa` (chỉ dùng ở lab; môi trường thật phải dùng user chỉ-đọc).
2. Tạo 2 câu hỏi giống nhau: "Doanh thu ngày (cũ)" từ `dbo.daily_revenue` và "Doanh thu ngày (mới)" từ `marts.mart_daily_revenue`. Dashboard "Báo cáo doanh thu" ban đầu dùng bản **cũ**.
3. **Cutover:** làm đúng các bước ở mục 4 (bỏ bước 3 nếu muốn nhanh), thay thẻ trên dashboard bằng bản mới. Bấm giờ.
4. **Rollback:** giả lập sự cố (ví dụ lặp lại ca 2 ở Tuần 5: sửa tay một dòng làm đối soát FAIL), làm theo mục 6. Bấm giờ.
5. Ghi `docs/evidence/tuan6-dien-tap-cutover.md`: thời gian từng bước, run_id, ảnh chụp, những gì không như kế hoạch và cách sửa kế hoạch.
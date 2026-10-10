# Bằng chứng đối soát

## 8. Cố tình tạo lỗi và chứng minh đối soát bắt được

Thực hiện trên Docker Compose local ngày 2026-10-10. Mỗi ca được chạy trên
snapshot tương ứng; các ca thay đổi dữ liệu được khôi phục trước khi chuyển
sang ca tiếp theo.

### Ca 1 — Lệch múi giờ ở `order_day`

Đổi `order_day` trong `stg_orders.sql` sang ngày giờ `Asia/Ho_Chi_Minh`, trong
khi stored procedure cũ nhóm ngày UTC. `make dbt-build` vẫn thành công với
`PASS=63`, `ERROR=0`: test dbt xác nhận tổng doanh thu khớp nhưng không xác nhận
doanh thu ở từng ngày.

| Run | Trạng thái |
|---|---|
| `manual__6db55fb8b84e` | `daily_revenue` FAIL; `cumulative_revenue` FAIL; 5 báo cáo còn lại PASS |

- `daily_revenue`: 181 dòng lệch ở L4; số dòng cũ 183, mới 184; sáu nhóm
  tháng lệch ở L3.
- `cumulative_revenue`: 181 dòng lệch ở L4; lệch lan truyền từ doanh thu ngày.
- Ví dụ ngày `2026-04-01`: `order_count` cũ 109, mới 78;
  `gross_revenue` cũ `3,231,672,000.00`, mới `2,053,163,000.00`.
- Tổng doanh thu vẫn được dbt test xác nhận khớp; lỗi là phân bổ sang ngày
  khác, nên kiểm tra theo từng khóa ngày mới phát hiện được.

Hoàn tác biểu thức múi giờ, chạy lại dbt rồi đối soát:
`manual__7fb3e21aa56d` — cả 7 báo cáo PASS.

### Ca 2 — Sửa tay một dòng báo cáo cũ

Tăng `dbo.customer_ltv.total_spent` thêm 1.000 cho `customer_id=1007`. ID `7`
trong hướng dẫn không tồn tại trong bộ dữ liệu hiện tại, nên dùng khóa có thật
để tạo đúng một dòng lệch.

| Run | Trạng thái |
|---|---|
| `manual__5cc59730ddfc` | `customer_ltv` FAIL; 6 báo cáo còn lại PASS |

- `sum(total_spent)`: SQL Server `452,563,013,000.00`, dbt
  `452,563,012,000.00`, chênh đúng `1,000.00`.
- L3 cohort lệch 1 nhóm; L4 lệch đúng 1 dòng.
- Dòng tiêu biểu: khóa `{"customer_id": 1007}`, cột `total_spent`,
  SQL Server `304,773,000.00`, dbt `304,772,000.00`.

Chạy `make legacy-batch` tính lại báo cáo cũ, sau đó
`manual__a0ca7f505ce9` — cả 7 báo cáo PASS.

### Ca 3 — Nguồn thay đổi sau lần ingest

Sau khi raw đã được ingest, chạy
`make simulate ARGS="--order-update 5 --order-insert 3"`, rồi chạy batch cũ
trên nguồn mới.

| Run | Trạng thái |
|---|---|
| `manual__519fe8f1c347` | Cả 7 báo cáo SKIP, không có dòng FAIL |

Snapshot ở batch cũ so với raw:

| Bảng | Batch cũ `{rows, max_rowver}` | Raw `{rows, max_rowver}` |
|---|---|---|
| `customers` | `{2018, 236014}` | `{2015, 218023}` |
| `orders` | `{20051, 236045}` | `{20048, 218243}` |
| `order_items` | `{60305, 236044}` | `{60296, 218240}` |

Với `--ignore-snapshot`, run `manual__91311cdd4a82` đánh dấu cả 7 báo cáo
FAIL dù hai phía đại diện cho các lát cắt nguồn khác nhau: `daily_revenue` 1,
`customer_ltv` 8, `customer_segments` 4, `product_sales` 14,
`cumulative_revenue` 1, `top_products_by_category` 4 và
`category_monthly_revenue` 10 dòng lệch. Snapshot guard tránh báo những FAIL
giả này.

### Khôi phục và bằng chứng dashboard

Trigger DAG `ingest_legacy` trong Airflow, không trigger trực tiếp DAG
reconciliation. Run `manual__2026-10-10T16:23:05.253153+00:00` thành công; DAG
`transform_dbt` và `legacy_nightly_batch` tự chạy, tiếp đó DAG `reconciliation`
thành công với run
`asset_triggered__2026-10-10T16:23:29.218050+00:00_QRyTLSMb`. Cả 7 báo cáo
PASS.

Q1 được lưu dạng biểu đồ cột xếp chồng. Ảnh dashboard được chụp lại khi tái
hiện Ca 2 để có trạng thái FAIL cùng các báo cáo PASS trên một màn hình. Run
`manual__d20309128f47` cho `customer_ltv` FAIL và 6 báo cáo còn lại PASS; Q2
làm nổi bật ô FAIL, Q5/Q6 hiển thị chi tiết.

Sau khi chụp, trigger `ingest_legacy` lần cuối để xóa lỗi thử nghiệm và ingest
các thay đổi nguồn. Cả chuỗi hoàn tất thành công:

| DAG | Run | Trạng thái |
|---|---|---|
| `ingest_legacy` | `manual__2026-10-10T16:39:49.790338+00:00` | success |
| `transform_dbt` | `asset_triggered__2026-10-10T16:39:55.078838+00:00_5mqrhw7I` | success |
| `legacy_nightly_batch` | `asset_triggered__2026-10-10T16:39:55.078830+00:00_xs1HVBDW` | success |
| `reconciliation` | `asset_triggered__2026-10-10T16:40:07.103749+00:00_P4pm1aUe` | success |

Run reconciliation cuối có cả 7 báo cáo PASS và `diff_rows=0`; lỗi có chủ ý
đã được khôi phục.

Sau lần chụp ảnh cập nhật, chạy `make legacy-batch`
(`manual__aeb1e21c0108`) để khôi phục báo cáo cũ, rồi chạy `make recon`
(`manual__4075773f0066`). Cả 7 báo cáo PASS, `diff_rows=0`.

![Dashboard đối soát với cả PASS và FAIL](./images/recon-dashboard.png)

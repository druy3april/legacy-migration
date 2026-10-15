# Kịch bản video demo (3–5 phút)

Mục tiêu: người xem hiểu bài toán, thấy pipeline chạy thật và tin rằng số liệu
mới khớp số liệu cũ. Quay màn hình 1080p, phóng to terminal (cỡ chữ ≥ 16).

## Chuẩn bị trước khi quay

```bash
make up && make wh && make minio && make airflow && make metabase
make airflow-pass              # mật khẩu đăng nhập Airflow
make readiness                 # để có bảng ngày xanh mới nhất
```

Mở sẵn các tab: Airflow (`localhost:8080`, màn hình Asset/Graph), dashboard
Metabase (`localhost:3000`), dbt docs (`make dbt-docs`, `localhost:8081`), tab
Actions trên GitHub có một lần CI xanh, và file `docs/cutover_plan.md`.

## Kịch bản

| Thời gian | Màn hình | Nói gì |
|---|---|---|
| 0:00–0:30 | README, sơ đồ kiến trúc | Bài toán: 7 báo cáo chạy bằng stored procedure trên SQL Server, không test, không cảnh báo. Mục tiêu: chuyển sang Airflow + dbt **mà không làm sai số**. |
| 0:30–1:15 | `sql/02_stored_procedures.sql`, rồi model dbt tương ứng | Ví dụ procedure dùng CURSOR và WHILE; bản dbt là một `CASE WHEN` và một window function trên bảng lịch. |
| 1:15–2:00 | Airflow: trigger `ingest_legacy`, xem chuỗi DAG tự chạy qua Asset | Tải tăng dần bằng `rowversion`, chạy lại không trùng, xóa ở nguồn được đánh dấu. dbt và job cũ tự chạy, đối soát chạy khi cả hai xong. |
| 2:00–3:00 | Dashboard Metabase: Q1, Q2, Q4, Q5 | 5 cấp đối soát. Kể Ca 1: dbt test vẫn xanh nhưng đối soát bắt được lệch múi giờ ở từng ngày. |
| 3:00–3:40 | GitHub Actions, file `ci/assert_expected_marts.sql`, `terraform plan` | Mỗi pull request: lint, unit test, dbt build trên dữ liệu mẫu, so con số kỳ vọng, Terraform plan. |
| 3:40–4:30 | `make readiness`, `docs/cutover_plan.md` | Điều kiện chuyển: 5 ngày xanh liên tiếp. Rollback chỉ là đổi nguồn báo cáo vì hệ thống cũ chạy song song 14 ngày. |
| 4:30–5:00 | README, mục số liệu | Tóm tắt con số: 7 procedure, khoảng 60.000 dòng chi tiết đơn, 12 model và 49 test dbt, 3 ca lỗi cố ý đều bị bắt. |

## Mẹo

- Quay từng đoạn rồi ghép, đừng cố quay một lần.
- Đọc trước câu mở đầu; phần còn lại nói tự nhiên theo màn hình.
- Đăng video (YouTube để chế độ không công khai) và gắn link vào README.

## Video đã xuất ngày 15/10/2026

Video portfolio 180 giây, 1280×720 H.264, chữ tiếng Việt, không lồng tiếng:
[legacy-migration-demo.mp4](./legacy-migration-demo.mp4). Nguồn và cách tái xuất
ở `demo/README.md`. Nội dung là minh họa kiến trúc và bằng chứng kiểm tra, không
phải quay trực tiếp thao tác trên ứng dụng. Video ghi rõ hiện 1/5 ngày xanh.

# Đối chiếu nhanh SQL Server và dbt

Thực hiện ngày 2026-10-09 trên Docker Compose local, không chạy `simulate`
trong lúc đối chiếu.

## Trình tự chạy

1. Trigger DAG `ingest_legacy` qua Airflow CLI:
   `manual__step5_reconciliation_20261009T0920` — trạng thái `success`.
2. Chạy `make batch` để làm mới các báo cáo SQL Server.
3. Chạy `make dbt-build` — hoàn tất với `PASS=63`, `ERROR=0`.
4. Truy vấn tổng hợp trên SQL Server và Postgres.

## Tổng hợp báo cáo

| Báo cáo | SQL Server dòng | SQL Server tổng | dbt dòng | dbt tổng | Kết quả |
|---|---:|---:|---:|---:|---|
| daily | 182 | 479,540,481,000.00 | 182 | 479,540,481,000.00 | Khớp |
| ltv | 2,012 | 452,053,029,000.00 | 2,012 | 452,053,029,000.00 | Khớp |
| product | 57 | 452,053,029,000.00 | 57 | 452,053,029,000.00 | Khớp |
| cumul | 192 | 479,540,481,000.00 | 192 | 479,540,481,000.00 | Khớp |
| top3 | 15 | 184,818,460,000.00 | 15 | 184,818,460,000.00 | Khớp |

## Phân khúc khách hàng

| Segment | SQL Server | dbt |
|---|---:|---:|
| CASUAL | 239 | 239 |
| DORMANT | 146 | 146 |
| INACTIVE | 13 | 13 |
| REGULAR | 883 | 883 |
| VIP | 731 | 731 |

## Số dòng nguồn và raw

| Bảng | SQL Server nguồn | Postgres raw hiện hành | Raw tombstone |
|---|---:|---:|---:|
| customers | 2,012 | 2,012 | 0 |
| products | 60 | 60 | 0 |
| orders | 20,008 | 20,008 | 0 |
| order_items | 60,222 | 60,222 | 3 |

`Raw hiện hành` là số dòng có `_deleted_at IS NULL`. Raw `order_items` có tổng
60,225 dòng vì giữ lại ba dòng đã bị xóa cứng ở nguồn; cả ba đã được
`detect_deletes` đánh dấu tombstone. So sánh số dòng hiện hành với nguồn cho
thấy không có chênh lệch.

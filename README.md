# Legacy migration

Dự án mô phỏng chuyển đổi hệ thống bán lẻ từ SQL Server với batch T-SQL sang
pipeline dữ liệu dùng Airflow, MinIO, PostgreSQL và dbt.

## 0. Tiến độ

| Tuần | Nội dung | Trạng thái |
|---|---|---|
| 1 | Dựng hệ thống nguồn SQL Server và batch T-SQL | Hoàn thành |
| 2 | Ingestion tăng dần qua Airflow, Parquet/MinIO và raw PostgreSQL | Hoàn thành |
| 3–4 | Chuyển 7 stored procedure sang dbt, kiểm thử và đối soát | Hoàn thành |
| 5 | Kiểm thử snapshot và đối soát dữ liệu | Sắp thực hiện |
| 6 | Hoàn thiện tài liệu dự án | Sắp thực hiện |

## Kiến trúc

```mermaid
flowchart LR
    SQL[SQL Server<br/>Nguồn và batch T-SQL]
    AIR[Airflow<br/>Ingestion và điều phối]
    S3[MinIO<br/>Parquet]
    RAW[PostgreSQL<br/>Raw và watermark]
    DBT[dbt<br/>Staging, intermediate, marts]
    OUT[Báo cáo]

    SQL --> AIR
    AIR --> S3
    S3 --> RAW
    RAW --> DBT
    DBT --> OUT
```

**Lưu ý đối soát:** `make ingest-all` không chạy `detect_deletes`. Khi cần
đối soát dữ liệu sau khi nguồn có xóa cứng, hãy chạy ingestion qua DAG
`ingest_legacy`; bước `detect_deletes` trong DAG sẽ đánh dấu tombstone ở raw.

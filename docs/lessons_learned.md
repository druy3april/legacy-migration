# Bài học rút ra

## 1. Watermark an toàn với transaction đang mở

- **Triệu chứng:** Nếu chốt watermark bằng `@@DBTS = 200062` trong lúc transaction giữ rowversion `200062` còn mở, sau khi transaction commit, điều kiện `row_ver > watermark` sẽ bỏ sót dòng đó vĩnh viễn.
- **Nguyên nhân:** `@@DBTS` có thể bao gồm rowversion chưa commit; trong lần tái hiện local, `MIN_ACTIVE_ROWVERSION() = 200062` khi transaction còn mở.
- **Cách sửa:** Dùng `MIN_ACTIVE_ROWVERSION() - 1` làm cận trên an toàn; lần quan sát này cho kết quả `200061`, nên rowversion `200062` chỉ được đọc ở lượt sau khi transaction đã commit.

## 2. Báo lỗi cho Airflow

- **Triệu chứng:** Task Airflow hiện xanh dù thao tác ETL bên trong thất bại.
- **Nguyên nhân:** Callable trả về `1` chỉ là một giá trị kết quả bình thường; Airflow không diễn giải nó như exit code lỗi của tiến trình.
- **Cách sửa:** Ném exception khi có lỗi (ví dụ `AirflowFailException` cho lỗi không retry); chỉ dùng exit code `1` ở entry point chạy như script/tiến trình độc lập.

## 3. Giữ đủ ngày trong doanh thu lũy kế

- **Triệu chứng:** Các ngày không có đơn biến mất khỏi mart lũy kế, khác với kết quả procedure cũ.
- **Nguyên nhân:** Window function chỉ duyệt các ngày có trong `mart_daily_revenue`, trong khi vòng `WHILE` cũ bước qua mọi ngày giữa ngày đầu và cuối.
- **Cách sửa:** Sinh date spine bằng `generate_series`, `LEFT JOIN` doanh thu ngày và thay giá trị thiếu bằng 0 trước khi tính running total.

## 4. Không import code dùng chung từ module DAG

- **Triệu chứng:** Airflow báo `AirflowDagDuplicatedIdException` khi DAG transform import callback từ `ingest_legacy.py`.
- **Nguyên nhân:** Import module Python chạy phần top-level; cuối file ingestion gọi `ingest_legacy()` và đăng ký cùng DAG ID lần nữa.
- **Cách sửa:** Đặt callback và Asset dùng chung trong package `airflow/dags/common/`; các DAG import từ đó, không import module DAG khác.

## 5. Chỉ ghi audit row count sau lần build thành công

- **Triệu chứng:** Test phát hiện mart giảm dòng mất tác dụng ở lần chạy kế tiếp sau một build lỗi.
- **Nguyên nhân:** Nếu lần lỗi vẫn cập nhật bảng audit, số liệu hỏng trở thành baseline mới để so sánh.
- **Cách sửa:** Hook `log_row_counts` kiểm tra trạng thái toàn bộ kết quả và chỉ ghi baseline khi không có model hoặc test nào `error`/`fail`.

## 6. Đo freshness trên log ingestion, không trên từng dòng raw

- **Triệu chứng:** Source raw bị báo cũ dù DAG vẫn chạy đều.
- **Nguyên nhân:** Với incremental upsert, `_loaded_at` của một dòng chỉ đổi khi bản ghi đó được nạp lại; không có thay đổi ở nguồn thì timestamp của dòng vẫn cũ.
- **Cách sửa:** Đo freshness bằng `etl.ingest_log.loaded_at`, nơi mỗi lần chạy đều ghi một dòng cho từng bảng, kể cả batch không có dòng mới.

## 7. dbt test xanh không đồng nghĩa khớp hệ thống cũ

- **Triệu chứng:** Ca 1, `make dbt-build` xanh nhưng `daily_revenue` và
  `cumulative_revenue` lệch theo ngày.
- **Nguyên nhân:** Test dbt xác nhận tổng doanh thu, không xác nhận phân bổ
  doanh thu trên từng khóa ngày.
- **Cách sửa:** Đối soát theo nhóm và từng dòng; tự động chạy reconciliation
  sau mỗi lần dbt build thành công.

## 8. Tránh tên file DAG trùng tên package

- **Triệu chứng:** Airflow có thể báo `ImportError` hoặc import nhầm module khi
  phân giải import của DAG.
- **Nguyên nhân:** Thư mục `dags/` nằm trên `sys.path`; file DAG trùng tên
  package/module dùng chung có thể che khuất module cần import.
- **Cách sửa:** Đặt tên file DAG khác tên package. DAG đối soát dùng
  `reconcile_legacy_vs_dbt.py`, còn code tái sử dụng nằm trong package riêng.

## 9. Lệch do thời điểm cắt dữ liệu không phải lỗi logic

- **Triệu chứng:** Ca 3 cho thấy cả 7 báo cáo có thể lệch nếu batch cũ chạy
  trên nguồn mới hơn lần ingestion.
- **Nguyên nhân:** Hai phía được tính từ hai fingerprint nguồn khác nhau; so
  trực tiếp sẽ tạo FAIL giả.
- **Cách sửa:** Gắn fingerprint vào batch và raw; nếu snapshot không khớp thì
  `SKIP` tại L0, chạy lại trên cùng snapshot. Nếu `SKIP` kéo dài, xử lý như
  sự cố vận hành.

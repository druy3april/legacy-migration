# Bài học rút ra

## 1. Watermark an toàn với transaction đang mở

- **Triệu chứng:** Nếu chốt watermark bằng `@@DBTS = 200062` trong lúc transaction giữ rowversion `200062` còn mở, sau khi transaction commit, điều kiện `row_ver > watermark` sẽ bỏ sót dòng đó vĩnh viễn.
- **Nguyên nhân:** `@@DBTS` có thể bao gồm rowversion chưa commit; trong lần tái hiện local, `MIN_ACTIVE_ROWVERSION() = 200062` khi transaction còn mở.
- **Cách sửa:** Dùng `MIN_ACTIVE_ROWVERSION() - 1` làm cận trên an toàn; lần quan sát này cho kết quả `200061`, nên rowversion `200062` chỉ được đọc ở lượt sau khi transaction đã commit.

## 2. Báo lỗi cho Airflow

- **Triệu chứng:** Task Airflow hiện xanh dù thao tác ETL bên trong thất bại.
- **Nguyên nhân:** Callable trả về `1` chỉ là một giá trị kết quả bình thường; Airflow không diễn giải nó như exit code lỗi của tiến trình.
- **Cách sửa:** Ném exception khi có lỗi (ví dụ `AirflowFailException` cho lỗi không retry); chỉ dùng exit code `1` ở entry point chạy như script/tiến trình độc lập.

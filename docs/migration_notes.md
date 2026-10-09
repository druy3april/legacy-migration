# Ghi chú chuyển đổi 7 stored procedure sang dbt

Các model staging loại bản ghi có `_deleted_at IS NOT NULL` trước khi tính toán.
Vì vậy mart thể hiện trạng thái hiện hành của nguồn thay vì giữ doanh thu của
các dòng đã xóa cứng. Các kết quả dưới đây đã được đối chiếu sau khi chạy DAG
ingestion, `make batch` và `make dbt-build`; số dòng, tổng tiền và phân bố
segment khớp trong lần đối chiếu ngày 2026-10-09
([bằng chứng](./evidence/dbt-sqlserver-reconciliation.md)).

## 1. `sp_refresh_daily_revenue` → `mart_daily_revenue`

- **Logic T-SQL:** `TRUNCATE` bảng đích rồi `GROUP BY CAST(order_date AS DATE)`,
  đếm đơn và cộng `total_amount`; chỉ loại `CANCELLED`.
- **Cách chuyển:** dbt table model nhóm staging orders theo `order_day`; mỗi lần
  build tính lại toàn bộ bảng thay cho `TRUNCATE`/`INSERT`.
- **Điểm khó:** Giữ đúng tập trạng thái: điều kiện `status <> 'CANCELLED'`
  vẫn tính đơn `NEW`, khác với các báo cáo chỉ tính đơn đã thanh toán.
- **Có thể lệch:** Nếu vô tình dùng danh sách trạng thái đã thanh toán sẽ thiếu
  doanh thu NEW. So sánh cả `order_count` lẫn `gross_revenue`, không chỉ tổng tiền.

## 2. `sp_refresh_customer_ltv` → `mart_customer_ltv`

- **Logic T-SQL:** Gom số đơn, tổng chi tiêu và ngày đầu/cuối từ đơn
  `PAID`/`SHIPPED`/`COMPLETED` vào `#order_totals`, sau đó `LEFT JOIN` mọi khách
  để khách chưa mua vẫn có LTV bằng 0.
- **Cách chuyển:** Hai tầng bảng tạm thành CTE; `ISNULL` thành `COALESCE`,
  `CONVERT(DATE, ...)` thành cast sang `date`.
- **Điểm khó:** Giữ toàn bộ khách bằng `LEFT JOIN`, đồng thời chỉ tổng hợp các
  trạng thái đã thanh toán trở lên.
- **Có thể lệch:** Dùng `INNER JOIN` sẽ làm mất khách chưa mua; thêm `NEW` hoặc
  `CANCELLED` vào status list sẽ tăng LTV. Khi `order_count = 0`, ngày đầu/cuối
  vẫn `NULL`.

## 3. `sp_refresh_customer_segments` → `mart_customer_segments`

- **Logic T-SQL:** Cursor đi qua LTV của từng khách và xét `IF/ELSE IF` theo
  thứ tự: `INACTIVE`, `DORMANT`, `VIP`, `REGULAR`, còn lại `CASUAL`.
- **Cách chuyển:** Một biểu thức `CASE` theo tập hợp, dùng các biến dbt
  `segment_as_of`, `dormant_days`, `vip_threshold`, `regular_threshold`.
- **Điểm khó:** Thứ tự nhánh là một phần của nghiệp vụ; ví dụ khách đủ ngưỡng
  VIP nhưng cũng quá hạn vẫn được xếp `DORMANT` vì nhánh này đứng trước.
- **Có thể lệch:** Ngày chốt là `2026-09-30`; thay ngày hoặc ngưỡng sẽ thay đổi
  phân bố. Biên dormant là lớn hơn 60 ngày, không phải lớn hơn hoặc bằng.

## 4. `sp_refresh_product_sales` → `mart_product_sales`

- **Logic T-SQL:** Tính units, doanh thu và ngày bán cuối từ order items thuộc
  đơn đã thanh toán; `MERGE` cập nhật/thêm sản phẩm và xóa target không còn trong
  nguồn.
- **Cách chuyển:** dbt table model nhóm lại toàn bộ staging order items và
  orders; full-table materialization tạo cùng trạng thái cuối như nhánh upsert
  cộng delete của `MERGE`.
- **Điểm khó:** Tính line revenue một lần ở staging, rồi cộng
  `quantity * unit_price`; chỉ lấy status đã thanh toán.
- **Có thể lệch:** Nếu một sản phẩm không còn dòng bán hợp lệ, nó không xuất
  hiện trong mart sau lần build, tương đương nhánh `NOT MATCHED BY SOURCE THEN
  DELETE`. Sản phẩm chưa bán không có dòng với doanh thu 0.

## 5. `sp_refresh_category_monthly_revenue` → intermediate và mart ngang

- **Logic T-SQL:** Dựng danh sách tháng bằng SQL động từ mọi đơn hàng, rồi
  `PIVOT` doanh thu item đã thanh toán theo danh mục và tháng.
- **Cách chuyển:** `int_category_monthly_revenue` giữ dữ liệu dạng dài
  (category, year_month, revenue); `mart_category_monthly_revenue` pivot các
  tháng thành cột để tương thích báo cáo cũ.
- **Điểm khó:** Cột tháng phụ thuộc dữ liệu nên schema mart thay đổi theo thời
  gian. ADR-0003 giải thích vì sao dạng dài là nguồn chính còn dạng ngang chỉ là
  lớp tương thích.
- **Có thể lệch:** Danh sách cột tháng đến từ mọi đơn, kể cả `NEW`/`CANCELLED`,
  nhưng doanh thu chỉ đến từ status đã thanh toán. Tháng chỉ có đơn chưa thanh
  toán có thể có cột nhưng giá trị `NULL`; khi chưa có tháng nào thì pivot
  động phải được xem xét riêng.

## 6. `sp_refresh_cumulative_revenue` → `mart_cumulative_revenue`

- **Logic T-SQL:** Vòng `WHILE` đi từng ngày từ min đến max, lấy doanh thu ngày
  (0 nếu ngày không có đơn) rồi cộng vào running total.
- **Cách chuyển:** Tạo date spine bằng `generate_series`, left join
  `mart_daily_revenue`, điền 0 và dùng window `SUM` có thứ tự theo ngày.
- **Điểm khó:** Window trực tiếp trên daily revenue sẽ bỏ qua ngày trống; phải
  tạo lịch đầy đủ trước khi tính lũy kế.
- **Có thể lệch:** Đầu/cuối khoảng vẫn lấy từ ngày nhỏ nhất/lớn nhất có trong
  `mart_daily_revenue`, giống logic cũ. Nếu daily mart rỗng, cumulative mart
  cũng rỗng.

## 7. `sp_refresh_top_products_by_category` → `mart_top_products_by_category`

- **Logic T-SQL:** Dùng bảng tạm tính doanh thu theo sản phẩm, `CROSS APPLY` +
  `TOP (3)` chọn ba sản phẩm mỗi danh mục, rồi `ROW_NUMBER` đánh hạng.
- **Cách chuyển:** CTE tổng hợp và `ROW_NUMBER() OVER (PARTITION BY category
  ORDER BY revenue DESC, product_id)`, sau đó lọc rank không quá 3.
- **Điểm khó:** Kết quả chỉ có danh mục có ít nhất một sản phẩm bán trong các
  trạng thái hợp lệ; `TOP (3)` không đảm bảo đủ ba dòng nếu danh mục ít sản
  phẩm.
- **Có thể lệch:** Procedure gốc không quy định tie-break khi doanh thu bằng
  nhau; dbt dùng `product_id` để thứ tự ổn định. Hai kết quả có thể chọn khác
  sản phẩm ở ranh giới top 3 nếu hòa doanh thu; cần thống nhất quy tắc nghiệp vụ
  nếu yêu cầu trùng tuyệt đối trong trường hợp hòa.

## Trình tự đối soát

Để so sánh cùng một lát cắt dữ liệu: chạy ingestion thành công, chạy
`make batch`, chạy `make dbt-build`, rồi đối chiếu số dòng/tổng tiền và số khách
theo segment. Không chạy `simulate` giữa các bước. Kết quả đã lưu tại
[`evidence/dbt-sqlserver-reconciliation.md`](./evidence/dbt-sqlserver-reconciliation.md).

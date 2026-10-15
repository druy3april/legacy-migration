# Ước tính chi phí: hệ thống báo cáo cũ so với nền tảng trên AWS

Baseline giá: **2026-10-11**, rà lại nguồn Redshift/MWAA ngày **2026-10-15**. Tất cả số tiền tính bằng USD/tháng (30 ngày, 730 giờ).
Đây là ước tính để so sánh phương án, không phải báo giá. Giá thay đổi theo
thời gian và theo region, nên trước khi trình bày cần tra lại trên
[AWS Pricing Calculator](https://calculator.aws/) với region thực tế.

## 1. Giả định

### Phạm vi

- Chỉ tính **khối lượng công việc báo cáo**: job ban đêm, 7 bảng báo cáo và
  dashboard. SQL Server của ứng dụng bán hàng vẫn giữ nguyên sau di chuyển nên
  không nằm trong so sánh.
- Giả định hiện tại báo cáo chạy trên **một SQL Server riêng cho báo cáo** (nhận
  dữ liệu sao chép từ server ứng dụng). Đây là phần có thể tắt sau cutover.
- Không tính chi phí một lần của dự án di chuyển (công sức xây dựng, đào tạo).

### Khối lượng dữ liệu

| | Quy mô hiện tại (lab) | Gấp 100 lần |
|---|---|---|
| Đơn hàng | ~20.000 trong 6 tháng (~110 đơn/ngày) | ~2 triệu (~11.000 đơn/ngày) |
| Dòng chi tiết đơn | ~60.000 | ~6 triệu |
| Dung lượng Parquet + lịch sử trên S3 | dưới 1 GB | ~10 GB |
| Dung lượng warehouse | dưới 1 GB | ~10 GB |
| Thời gian warehouse có truy vấn mỗi ngày (ingest, dbt build, đối soát, dashboard) | ~15 phút | ~2 giờ |
| Giờ vận hành mỗi tháng (xử lý job lỗi, sửa logic, đối chiếu tay) | Cũ: 10 giờ · Mới: 4 giờ | Cũ: 20 giờ · Mới: 6 giờ |

Giờ vận hành là giả định của dự án: hệ thống mới có test, cảnh báo và đối soát
tự động nên ít phải kiểm tra tay. Gọi `R` là chi phí một giờ công (USD/giờ) để
bạn tự điền theo thực tế.

### Region

Trang giá chính thức của AWS chỉ hiển thị sẵn số liệu ví dụ của **US East (N.
Virginia)**, nên bảng dưới dùng giá us-east-1. Region gần Việt Nam là
ap-southeast-1 (Singapore); bảng này chưa phải dự toán triển khai Singapore.
Để minh họa plan cùng region với bảng giá: `TF_VAR_aws_region=us-east-1 make tf-plan`.
Nếu đổi region sang Singapore, tạo lại estimate từ Pricing Calculator với region đó
và lưu bản xuất estimate. Không chỉ đổi nhãn region trên bảng giá.

Ngày rà soát nguồn: 2026-10-15; các số dưới đây là baseline tham khảo theo trang
nguồn, chưa phải báo giá đầy đủ. Chưa gồm S3 requests, network/NAT, logging,
backup, BI hosting, thuế và chi phí di chuyển. Mục đích học tập; phải bổ sung các
hạng mục này trước khi quyết định ngân sách.

## 2. Đơn giá đã tra

| Hạng mục | Đơn giá | Nguồn |
|---|---|---|
| S3 Standard, lưu trữ | $0,023 / GB-tháng (50 TB đầu) | [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/) (bảng giá hiển thị bằng JavaScript, cần xác nhận lại trên trang) |
| Redshift Serverless, tính toán | $0,375 / RPU-giờ, tính theo giây, tối thiểu 60 giây mỗi lần; dung lượng cơ sở từ 4 RPU | [Amazon Redshift pricing](https://aws.amazon.com/redshift/pricing/) |
| Redshift Managed Storage | $0,024 / GB-tháng | [Amazon Redshift pricing](https://aws.amazon.com/redshift/pricing/) |
| Amazon MWAA, môi trường Small | $0,49 / giờ | [Amazon MWAA pricing](https://aws.amazon.com/managed-workflows-for-apache-airflow/pricing/) |
| Amazon MWAA, lưu metadata | $0,10 / GB-tháng | như trên |
| Secrets Manager | $0,40 / secret-tháng; $0,05 / 10.000 lần gọi API | [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/) |
| SQL Server 2025 Standard, thuê bao | $1.418 / năm cho gói 2 core (tối thiểu 4 core mỗi server) | Bảng giá SQL Server 2025 của Microsoft, theo [datasheet chính thức Microsoft](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/bade/documents/products-and-services/en-us/security/644401-sql-server-2025-pricing.pdf) |
| SQL Server 2025 Standard, mua đứt | $3.945 / gói 2 core (giá bán lẻ ước tính) | như trên |

Môi trường lab dùng SQL Server **Developer**, miễn phí nhưng không được dùng cho
môi trường production.

## 3. Hệ thống cũ (SQL Server báo cáo)

| Hạng mục | Lab | Gấp 100 lần | Cách tính |
|---|---:|---:|---|
| License SQL Server Standard (thuê bao) | 236,33 | 472,67 | 4 core = 2 gói × $1.418 / 12; gấp 100 lần cần 8 core = 4 gói |
| Máy chủ (khấu hao 36 tháng) | 166,67 | 277,78 | **Giả định** máy $6.000 và $10.000; thay bằng số thật của công ty |
| **Hạ tầng** | **≈ 403** | **≈ 750** | |
| Vận hành | 10 × R | 20 × R | |

Chưa tính điện, phòng máy, sao lưu và bản quyền hệ điều hành.

## 4. Nền tảng mới trên AWS

Kiến trúc theo [terraform/](../terraform/README.md): S3 thay MinIO, Redshift
Serverless thay PostgreSQL, MWAA thay Airflow tự dựng.

| Hạng mục | Lab | Gấp 100 lần | Cách tính |
|---|---:|---:|---|
| S3 | 0,02 | 0,23 | 1 GB và 10 GB × $0,023 |
| Redshift Serverless, tính toán | 22,50 | 180,00 | 8 RPU × 0,25 giờ hoặc 2 giờ/ngày × 30 ngày × $0,375 |
| Redshift Managed Storage | 0,02 | 0,24 | 1 GB và 10 GB × $0,024 |
| MWAA Small | 357,70 | 357,70 | $0,49 × 730 giờ; môi trường chạy liên tục |
| MWAA metadata | 0,10 | 0,10 | 1 GB |
| Secrets Manager | 0,40 | 0,40 | 1 secret (mật khẩu SQL Server) |
| **Hạ tầng** | **≈ 381** | **≈ 539** | |
| Vận hành | 4 × R | 6 × R | |

Ở quy mô lab, Redshift dùng khoảng 60 RPU-giờ/tháng, dưới ngưỡng chặn 100
RPU-giờ đặt trong Terraform (`redshift_monthly_rpu_hours_limit`). Ở quy mô gấp
100 lần (~480 RPU-giờ) phải nâng ngưỡng này lên trước khi chạy thật.

## 5. So sánh

| | Lab | Gấp 100 lần |
|---|---|---|
| Hệ thống cũ | $403 + 10R | $750 + 20R |
| AWS | $381 + 4R | $539 + 6R |

Nhận xét:

1. **Ở quy mô nhỏ, tiền hạ tầng gần như ngang nhau.** Lợi ích chính là giảm
   giờ vận hành và giảm rủi ro sai số liệu (test, cảnh báo, đối soát), không
   phải tiết kiệm hạ tầng.
2. **MWAA chiếm khoảng 94% chi phí AWS ở quy mô lab** vì chạy liên tục bất kể
   khối lượng. Đây là chỗ đầu tiên cần tối ưu.
3. Với giả định thời gian truy vấn trong bảng, chi phí AWS tăng ít hơn. Đây
   là kết quả của giả định; cần benchmark khi tăng dữ liệu, không mặc định tăng 100 lần vẫn chỉ tốn 2 giờ/ngày.
4. Kết luận phụ thuộc mạnh vào giả định giá máy chủ và giờ vận hành; thay bằng
   số thật trước khi dùng để ra quyết định.

## 6. Cách giảm chi phí (cần tra giá trước khi chọn)

| Cách | Ảnh hưởng | Đánh đổi |
|---|---|---|
| Airflow tự dựng trên một máy ảo nhỏ thay MWAA | Bỏ phần chi phí lớn nhất | Tự vá lỗi, nâng cấp, sao lưu Airflow |
| Lớp MWAA nhỏ hơn Small hoặc dạng serverless nếu region hỗ trợ | Giảm chi phí cố định | Giới hạn số task và DAG chạy đồng thời |
| Athena + S3 thay Redshift khi dữ liệu còn nhỏ | Trả theo dung lượng quét, gần như 0 với vài GB | Dùng `dbt-athena`, cú pháp và hiệu năng khác |
| Giữ ngưỡng `usage_limit` của Redshift và cảnh báo ngân sách (AWS Budgets) | Chặn chi phí đột biến do truy vấn lỗi | Có thể dừng workgroup giữa tháng nếu đặt ngưỡng quá thấp |
| Gom dashboard đọc từ bảng mart thay vì truy vấn nặng trực tiếp | Giảm thời gian Redshift chạy | Cần thiết kế mart sát nhu cầu báo cáo |

## 7. Đối chiếu với hiện trạng lab

Default Terraform đã thống nhất `us-east-1` với kịch bản giá trong bảng. Không
apply cloud. MinIO thực đo ngày 15/10 có 58 object, 11.105.692 bytes, 5 manifest
(xem evidence/storage-2026-10-15.json). Đây là dung lượng hiện có, không phải
cam kết dung lượng cả tháng hoặc khi tăng 100 lần. Full snapshot tăng theo số
checkpoint; chưa có garbage collector xóa đồng bộ manifest và object tham chiếu.
Không bật expiry object đơn lẻ làm hỏng khả năng restore.

Các khoản requests/network/log/backup/BI chưa có cấu hình AWS triển khai nên
không gán giá giả để cộng vào tổng. Tổng trong bảng là phần baseline đã nêu,
không phải TCO triển khai hoàn chỉnh. Khi triển khai, dùng Pricing Calculator
và lưu estimate đầy đủ cùng region và traffic thực tế.

# Terraform: hạ tầng tương đương trên AWS (chỉ plan)

Code mô tả nền tảng dữ liệu khi đưa lên AWS. Default region `us-east-1`
để thống nhất với kịch bản chi phí; đổi region thì lập lại estimate. Dự án **không apply**: mục đích là
chứng minh kiến trúc local chuyển lên cloud được, và chạy được `validate`/`plan`
mà không cần tài khoản AWS.

| File | Tài nguyên | Thay cho (local) |
|---|---|---|
| `s3.tf` | Bucket data lake: versioning, mã hóa, chặn public, xóa phiên bản cũ sau 30 ngày | MinIO |
| `redshift.tf` | Redshift Serverless namespace + workgroup, giới hạn RPU-giờ mỗi tháng | PostgreSQL warehouse |
| `iam.tf` | Vai trò cho Airflow (đọc/ghi S3, chạy SQL, đọc secret) và cho Redshift (COPY từ S3) | — |
| `secrets.tf` | Secret chứa thông tin đăng nhập SQL Server cũ (giá trị nhập tay, không nằm trong code) | `.env` |

Airflow trên AWS (MWAA) cần VPC, subnet riêng và bucket chứa DAG nên được để cho
giai đoạn sau; chi phí của nó vẫn được tính trong
[docs/cost_estimate.md](../docs/cost_estimate.md).

## Cài Terraform trên Fedora

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager addrepo --from-repofile=https://rpm.releases.hashicorp.com/fedora/hashicorp.repo
sudo dnf -y install terraform
terraform -version
```

Fedora cũ dùng dnf4 thì thay dòng thứ hai bằng
`sudo dnf config-manager --add-repo https://rpm.releases.hashicorp.com/fedora/hashicorp.repo`.

## Chạy

```bash
make tf-fmt        # định dạng lại code
make tf-validate   # init + fmt -check + validate
make tf-plan       # plan với khóa giả: liệt kê tài nguyên sẽ tạo
```

Lần `init` đầu tiên tải provider AWS (vài trăm MB) vào `terraform/.terraform/`.
Thư mục này đã nằm trong `.gitignore`, **không commit**. File
`.terraform.lock.hcl` thì **phải commit** để mọi máy và CI dùng cùng phiên bản provider.

## Chế độ giả lập và chế độ thật

Mặc định `use_mock_credentials = true`: provider dùng khóa giả và bỏ qua các
bước gọi API xác thực. Vì state rỗng, `plan` chỉ cần so cấu hình với "không có
gì" nên không phải gọi AWS. Một số giá trị như ARN sẽ hiện `(known after apply)`.

Khi có tài khoản thật:

```bash
export AWS_PROFILE=<profile>
terraform -chdir=terraform plan -var use_mock_credentials=false
```

Trước khi `apply` thật cần thêm: backend lưu state từ xa (S3 + khóa), VPC/subnet
riêng cho Redshift thay vì VPC mặc định, và cảnh báo ngân sách (AWS Budgets).

## Lưu ý

- `redshift_base_rpu` mặc định 8 vì dùng được ở mọi region; region hỗ trợ 4 RPU
  thì có thể hạ xuống 4 để giảm chi phí.
- `manage_admin_password = true` để Redshift tự tạo mật khẩu admin và lưu trong
  Secrets Manager, không có mật khẩu nào trong code hay state.
- Khi đổi warehouse sang Redshift, vài model dbt phải sửa cú pháp; danh sách ở
  [docs/architecture.md](../docs/architecture.md), mục 7.

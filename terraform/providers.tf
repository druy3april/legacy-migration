# Chế độ giả lập (mặc định, use_mock_credentials = true): plan được mà không cần tài khoản AWS.
# Provider dùng khóa giả và bỏ qua các bước gọi API xác thực; vì state rỗng nên plan chỉ liệt kê
# tài nguyên sẽ tạo. Khi có tài khoản thật: terraform plan -var use_mock_credentials=false
# (thông tin đăng nhập lấy từ AWS_PROFILE hoặc biến môi trường như bình thường).
provider "aws" {
  region = var.aws_region

  access_key                  = var.use_mock_credentials ? "mock_access_key" : null
  secret_key                  = var.use_mock_credentials ? "mock_secret_key" : null
  skip_credentials_validation = var.use_mock_credentials
  skip_requesting_account_id  = var.use_mock_credentials
  skip_metadata_api_check     = var.use_mock_credentials

  default_tags {
    tags = local.tags
  }
}

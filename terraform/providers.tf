provider "aws" {
  region = var.aws_region

  # plan_only = true: chạy được `terraform plan` không cần tài khoản AWS
  # (CI và portfolio). Khi triển khai thật đặt plan_only = false và dùng credential thật.
  skip_credentials_validation = var.plan_only
  skip_requesting_account_id  = var.plan_only
  skip_metadata_api_check     = var.plan_only

  default_tags {
    tags = local.tags
  }
}
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Khi triển khai thật: lưu state trên S3 (tạo bucket state riêng trước).
  # backend "s3" {
  #   bucket       = "legacy-migration-tfstate-<hau-to>"
  #   key          = "dev/terraform.tfstate"
  #   region       = "ap-southeast-1"
  #   use_lockfile = true
  # }
}
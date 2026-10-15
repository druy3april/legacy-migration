variable "aws_region" {
  description = "Region minh họa, thống nhất với bảng chi phí us-east-1. Lập lại estimate nếu đổi region."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Tên dự án, dùng làm tiền tố tên tài nguyên."
  type        = string
  default     = "legacy-migration"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,17}$", var.project))
    error_message = "project chỉ gồm chữ thường, số, dấu gạch ngang; dài 3-18 ký tự (giới hạn bucket_prefix của S3)."
  }
}

variable "environment" {
  description = "Môi trường: dev, staging hoặc prod."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment phải là dev, staging hoặc prod."
  }
}

variable "use_mock_credentials" {
  description = "true = plan không cần tài khoản AWS (minh họa, chạy trong CI). false = dùng thông tin đăng nhập thật."
  type        = bool
  default     = true
}

variable "redshift_base_rpu" {
  description = "Dung lượng tính toán cơ sở của Redshift Serverless (RPU). Một số region cho phép 4; 8 dùng được ở mọi region."
  type        = number
  default     = 8

  validation {
    condition     = var.redshift_base_rpu >= 4 && var.redshift_base_rpu <= 1024
    error_message = "redshift_base_rpu phải trong khoảng 4-1024."
  }
}

variable "redshift_max_rpu" {
  description = "Trần RPU khi Redshift Serverless tự mở rộng, để chặn chi phí đột biến."
  type        = number
  default     = 32
}

variable "redshift_monthly_rpu_hours_limit" {
  description = "Số RPU-giờ tối đa mỗi tháng; vượt ngưỡng thì workgroup bị tạm dừng (xem docs/cost_estimate.md)."
  type        = number
  default     = 100
}

variable "noncurrent_version_retention_days" {
  description = "Số ngày giữ phiên bản cũ của file trên S3 trước khi xóa."
  type        = number
  default     = 30
}

variable "project" {
  description = "Tên dự án, dùng làm tiền tố tên tài nguyên"
  type        = string
  default     = "legacy-migration"
}

variable "environment" {
  description = "Môi trường: dev, staging, prod"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment phải là dev, staging hoặc prod."
  }
}

variable "aws_region" {
  description = "Region AWS (Singapore gần Việt Nam nhất)"
  type        = string
  default     = "ap-southeast-1"
}

variable "bucket_suffix" {
  description = "Hậu tố để tên bucket S3 là duy nhất toàn cầu (vd: tên GitHub)"
  type        = string
}

variable "raw_ia_after_days" {
  description = "Sau bao nhiêu ngày chuyển file Parquet vùng raw sang STANDARD_IA"
  type        = number
  default     = 30
}

variable "redshift_base_rpu" {
  description = "Dung lượng cơ sở Redshift Serverless (RPU)"
  type        = number
  default     = 8
}

variable "redshift_max_rpu" {
  description = "Trần RPU để chặn chi phí tăng đột biến"
  type        = number
  default     = 16
}

variable "monthly_budget_usd" {
  description = "Ngân sách tháng (USD), khớp docs/cost_estimate.md"
  type        = number
}

variable "alert_email" {
  description = "Email nhận cảnh báo pipeline và ngân sách; để trống thì không tạo subscription"
  type        = string
  default     = ""
}

variable "plan_only" {
  description = "true = chỉ chạy plan, không cần credential AWS thật"
  type        = bool
  default     = true
}
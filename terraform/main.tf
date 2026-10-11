locals {
  name = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Data lake: thay MinIO. Cùng cấu trúc key raw/<bang>/incremental/... (ADR-0002)
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "datalake" {
  bucket = "${local.name}-datalake-${var.bucket_suffix}"
}

resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket                  = aws_s3_bucket.datalake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    id     = "raw-sang-ia"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    transition {
      days          = var.raw_ia_after_days
      storage_class = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ---------------------------------------------------------------------------
# Warehouse: thay PostgreSQL. dbt chuyển sang adapter dbt-redshift.
# ---------------------------------------------------------------------------
resource "aws_redshiftserverless_namespace" "warehouse" {
  namespace_name        = "${local.name}-wh"
  db_name               = "warehouse"
  admin_username        = "wh_admin"
  manage_admin_password = true # mật khẩu do Secrets Manager quản lý, không nằm trong state
  iam_roles             = [aws_iam_role.warehouse.arn]
  default_iam_role_arn  = aws_iam_role.warehouse.arn
}

resource "aws_redshiftserverless_workgroup" "warehouse" {
  namespace_name      = aws_redshiftserverless_namespace.warehouse.namespace_name
  workgroup_name      = "${local.name}-wg"
  base_capacity       = var.redshift_base_rpu
  max_capacity        = var.redshift_max_rpu
  publicly_accessible = false
}

# ---------------------------------------------------------------------------
# Bí mật kết nối SQL Server nguồn. Chỉ tạo "vỏ"; giá trị nhập tay, không đưa vào code/state.
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "legacy_sqlserver" {
  name        = "${local.name}/legacy-sqlserver"
  description = "Thông tin kết nối SQL Server cũ cho task ingestion"
}

# ---------------------------------------------------------------------------
# Cảnh báo: thay email Gmail trong common/alerts.py
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "pipeline_alerts" {
  name = "${local.name}-pipeline-alerts"
}

resource "aws_sns_topic_subscription" "pipeline_alerts_email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_budgets_budget" "monthly" {
  count        = var.alert_email == "" ? 0 : 1
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
# Role cho Redshift đọc Parquet từ S3 (COPY / Spectrum)
data "aws_iam_policy_document" "redshift_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "warehouse" {
  name               = "${local.name}-warehouse"
  assume_role_policy = data.aws_iam_policy_document.redshift_assume.json
}

data "aws_iam_policy_document" "warehouse_read_raw" {
  statement {
    sid       = "DocVungRaw"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.datalake.arn}/raw/*"]
  }

  statement {
    sid       = "LietKeBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.datalake.arn]
  }
}

resource "aws_iam_role_policy" "warehouse_read_raw" {
  name   = "read-raw"
  role   = aws_iam_role.warehouse.id
  policy = data.aws_iam_policy_document.warehouse_read_raw.json
}

# Role cho Airflow (MWAA) chạy ingestion: ghi raw/, đọc secret nguồn, gửi cảnh báo
data "aws_iam_policy_document" "airflow_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["airflow.amazonaws.com", "airflow-env.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "pipeline" {
  name               = "${local.name}-pipeline"
  assume_role_policy = data.aws_iam_policy_document.airflow_assume.json
}

data "aws_iam_policy_document" "pipeline" {
  statement {
    sid       = "GhiDocDataLake"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.datalake.arn}/*"]
  }

  statement {
    sid       = "LietKeBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.datalake.arn]
  }

  statement {
    sid       = "DocSecretNguon"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.legacy_sqlserver.arn]
  }

  statement {
    sid       = "GuiCanhBao"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.pipeline_alerts.arn]
  }
}

resource "aws_iam_role_policy" "pipeline" {
  name   = "pipeline"
  role   = aws_iam_role.pipeline.id
  policy = data.aws_iam_policy_document.pipeline.json
}
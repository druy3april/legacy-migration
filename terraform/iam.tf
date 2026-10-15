# Hai vai trò theo nguyên tắc quyền tối thiểu:
#   pipeline       : Airflow (MWAA) đọc/ghi data lake, chạy SQL trên Redshift, đọc mật khẩu SQL Server
#   redshift_s3    : Redshift đọc Parquet từ data lake khi COPY vào schema raw

data "aws_iam_policy_document" "pipeline_assume" {
  statement {
    sid     = "AirflowAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["airflow.amazonaws.com", "airflow-env.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "pipeline" {
  name               = "${local.name}-pipeline"
  description        = "Airflow: ingestion SQL Server -> S3 -> Redshift, dbt build, doi soat"
  assume_role_policy = data.aws_iam_policy_document.pipeline_assume.json
}

data "aws_iam_policy_document" "pipeline" {
  statement {
    sid       = "ListDatalake"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.datalake.arn]
  }

  statement {
    sid       = "ReadWriteDatalakeObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.datalake.arn}/*"]
  }

  statement {
    sid       = "RunSqlOnWarehouse"
    effect    = "Allow"
    actions   = ["redshift-data:ExecuteStatement", "redshift-data:BatchExecuteStatement", "redshift-serverless:GetCredentials"]
    resources = [aws_redshiftserverless_workgroup.warehouse.arn]
  }

  statement {
    sid       = "ReadStatementResults"
    effect    = "Allow"
    actions   = ["redshift-data:DescribeStatement", "redshift-data:GetStatementResult", "redshift-data:CancelStatement", "redshift-data:ListStatements"]
    resources = ["*"]
  }

  statement {
    sid       = "ReadLegacySqlServerSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.legacy_sqlserver.arn]
  }
}

resource "aws_iam_role_policy" "pipeline" {
  name   = "${local.name}-pipeline"
  role   = aws_iam_role.pipeline.id
  policy = data.aws_iam_policy_document.pipeline.json
}

data "aws_iam_policy_document" "redshift_assume" {
  statement {
    sid     = "RedshiftAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "redshift_s3" {
  name               = "${local.name}-redshift-s3"
  description        = "Redshift Serverless doc Parquet tu data lake (COPY)"
  assume_role_policy = data.aws_iam_policy_document.redshift_assume.json
}

data "aws_iam_policy_document" "redshift_s3" {
  statement {
    sid       = "ListDatalake"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.datalake.arn]
  }

  statement {
    sid       = "ReadRawParquet"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.datalake.arn}/raw/*"]
  }
}

resource "aws_iam_role_policy" "redshift_s3" {
  name   = "${local.name}-redshift-s3"
  role   = aws_iam_role.redshift_s3.id
  policy = data.aws_iam_policy_document.redshift_s3.json
}

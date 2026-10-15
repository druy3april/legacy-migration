output "datalake_bucket" {
  description = "Tên bucket S3 thay cho MinIO (đặt vào MINIO_BUCKET khi chạy trên AWS)."
  value       = aws_s3_bucket.datalake.bucket
}

output "redshift_namespace" {
  description = "Namespace Redshift Serverless."
  value       = aws_redshiftserverless_namespace.warehouse.namespace_name
}

output "redshift_workgroup" {
  description = "Workgroup Redshift Serverless mà dbt kết nối tới."
  value       = aws_redshiftserverless_workgroup.warehouse.workgroup_name
}

output "pipeline_role_arn" {
  description = "Vai trò IAM cho Airflow (MWAA)."
  value       = aws_iam_role.pipeline.arn
}

output "redshift_s3_role_arn" {
  description = "Vai trò IAM để Redshift COPY từ S3."
  value       = aws_iam_role.redshift_s3.arn
}

output "legacy_sqlserver_secret_arn" {
  description = "Secret chứa thông tin đăng nhập SQL Server cũ."
  value       = aws_secretsmanager_secret.legacy_sqlserver.arn
}

output "datalake_bucket" {
  description = "Bucket thay cho MinIO"
  value       = aws_s3_bucket.datalake.bucket
}

output "redshift_workgroup" {
  description = "Workgroup Redshift Serverless cho dbt-redshift"
  value       = aws_redshiftserverless_workgroup.warehouse.workgroup_name
}

output "pipeline_role_arn" {
  description = "Execution role cho Airflow/MWAA"
  value       = aws_iam_role.pipeline.arn
}

output "alerts_topic_arn" {
  description = "SNS topic nhận cảnh báo pipeline"
  value       = aws_sns_topic.pipeline_alerts.arn
}
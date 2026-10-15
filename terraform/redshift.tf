# Warehouse thay cho PostgreSQL. Redshift Serverless tính tiền theo RPU-giờ khi có truy vấn,
# không tốn tiền tính toán lúc rảnh (chi tiết: docs/cost_estimate.md).
resource "aws_redshiftserverless_namespace" "warehouse" {
  namespace_name        = "${local.name}-ns"
  db_name               = "warehouse"
  admin_username        = "warehouse_admin"
  manage_admin_password = true
  iam_roles             = [aws_iam_role.redshift_s3.arn]
  default_iam_role_arn  = aws_iam_role.redshift_s3.arn
}

resource "aws_redshiftserverless_workgroup" "warehouse" {
  namespace_name      = aws_redshiftserverless_namespace.warehouse.namespace_name
  workgroup_name      = "${local.name}-wg"
  base_capacity       = var.redshift_base_rpu
  max_capacity        = var.redshift_max_rpu
  publicly_accessible = false
}

# Chốt chặn chi phí: vượt số RPU-giờ trong tháng thì tạm dừng workgroup.
resource "aws_redshiftserverless_usage_limit" "monthly_compute" {
  resource_arn  = aws_redshiftserverless_workgroup.warehouse.arn
  usage_type    = "serverless-compute"
  amount        = var.redshift_monthly_rpu_hours_limit
  period        = "monthly"
  breach_action = "deactivate"
}

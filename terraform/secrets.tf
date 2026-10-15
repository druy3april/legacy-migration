# Chỉ tạo "ngăn chứa" bí mật; giá trị (user/mật khẩu SQL Server) nhập tay trên console
# hoặc bằng AWS CLI, không bao giờ nằm trong code hay state của Terraform.
resource "aws_secretsmanager_secret" "legacy_sqlserver" {
  name                    = "${local.name}/legacy-sqlserver"
  description             = "Thong tin dang nhap SQL Server cua he thong cu (chi doc)"
  recovery_window_in_days = 7
}

#!/bin/bash
# Chạy lần lượt mọi file /sql/*.sql theo thứ tự tên file (00_, 01_, 02_...)
set -euo pipefail

SQLCMD=/opt/mssql-tools18/bin/sqlcmd

for f in /sql/*.sql; do
  [ -e "$f" ] || continue
  echo ">>> Đang chạy: $f"
  $SQLCMD -C -S sqlserver -U sa -P "$MSSQL_SA_PASSWORD" -b -i "$f"
done

echo ">>> sql-init hoàn tất"
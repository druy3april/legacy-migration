"""Kiểm tra Python kết nối được tới SQL Server (hệ thống cũ)."""
import os
import sys

import pymssql
from dotenv import load_dotenv

load_dotenv()  # đọc file .env ở thư mục gốc dự án


def main() -> int:
    try:
        conn = pymssql.connect(
            server=os.getenv("MSSQL_HOST", "localhost"),
            port=int(os.getenv("MSSQL_PORT", "1433")),
            user="sa",
            password=os.environ["MSSQL_SA_PASSWORD"],
            database=os.getenv("MSSQL_DATABASE", "LegacyRetail"),
            login_timeout=10,
        )
    except KeyError:
        print("Thiếu MSSQL_SA_PASSWORD, hãy tạo file .env từ .env.example")
        return 1
    except pymssql.Error as exc:
        print(f"Không kết nối được SQL Server: {exc}")
        return 1

    with conn:
        cur = conn.cursor()
        cur.execute("SELECT DB_NAME(), @@VERSION")
        db_name, version = cur.fetchone()
        print(f"Kết nối OK. Database: {db_name}")
        print(version.splitlines()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""Giả lập thay đổi ở hệ thống nguồn: sửa thành phố một số khách và thêm khách mới."""
import argparse
import random
import sys
import uuid

import pymssql
from faker import Faker

from generate_data import CITIES, get_connection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", type=int, default=5, help="số khách hàng bị sửa thành phố")
    parser.add_argument("--insert", type=int, default=3, help="số khách hàng thêm mới")
    args = parser.parse_args()

    fake = Faker("vi_VN")

    try:
        conn = get_connection()
    except KeyError:
        print("Thiếu MSSQL_SA_PASSWORD, hãy kiểm tra file .env")
        return 1
    except pymssql.Error as exc:
        print(f"Không kết nối được SQL Server: {exc}")
        return 1

    with conn:
        cur = conn.cursor()

        cur.execute("SELECT TOP (%s) customer_id FROM dbo.customers ORDER BY NEWID()", (args.update,))
        ids = [row[0] for row in cur.fetchall()]
        for customer_id in ids:
            cur.execute(
                "UPDATE dbo.customers SET city = %s WHERE customer_id = %s",
                (random.choice(CITIES), customer_id),
            )

        for _ in range(args.insert):
            cur.execute(
                "INSERT INTO dbo.customers (full_name, email, city) VALUES (%s, %s, %s)",
                (fake.name(), f"moi_{uuid.uuid4().hex[:10]}@example.com", random.choice(CITIES)),
            )

        conn.commit()

    print(f"Đã sửa {len(ids)} khách hàng: {ids}")
    print(f"Đã thêm {args.insert} khách hàng mới")
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""Giả lập thay đổi ở hệ thống nguồn: sửa thành phố một số khách và thêm khách mới."""
import argparse
import random
import sys
import uuid

import pymssql
from faker import Faker

from generate_data import CITIES, get_connection


def non_negative_int(value: str) -> int:
    count = int(value)
    if count < 0:
        raise argparse.ArgumentTypeError("giá trị phải lớn hơn hoặc bằng 0")
    return count


def update_orders(cur, count: int) -> int:
    cur.execute(
        "SELECT TOP (%s) order_id FROM dbo.orders "
        "WHERE status = 'NEW' ORDER BY NEWID()",
        (count,),
    )
    order_ids = [row[0] for row in cur.fetchall()]
    for order_id in order_ids:
        for status in ("PAID", "SHIPPED", "COMPLETED"):
            cur.execute(
                "UPDATE dbo.orders SET status = %s, updated_at = SYSUTCDATETIME() "
                "WHERE order_id = %s",
                (status, order_id),
            )
    return len(order_ids)


def insert_orders(cur, count: int) -> tuple[int, int]:
    if count == 0:
        return 0, 0

    cur.execute("SELECT customer_id FROM dbo.customers")
    customer_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT product_id, unit_price FROM dbo.products WHERE is_active = 1")
    products = cur.fetchall()
    if not customer_ids or not products:
        raise ValueError("Cần có khách hàng và sản phẩm đang bán để thêm đơn hàng")

    item_count = 0
    for _ in range(count):
        cur.execute(
            "INSERT INTO dbo.orders "
            "(customer_id, order_date, status, total_amount, updated_at) "
            "VALUES (%s, SYSUTCDATETIME(), 'NEW', 0, SYSUTCDATETIME())",
            (random.choice(customer_ids),),
        )
        cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
        order_id = cur.fetchone()[0]

        lines = random.sample(products, k=random.randint(1, min(3, len(products))))
        for product_id, unit_price in lines:
            cur.execute(
                "INSERT INTO dbo.order_items "
                "(order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, random.randint(1, 4), unit_price),
            )
            item_count += 1

        cur.execute(
            "UPDATE dbo.orders SET total_amount = "
            "(SELECT COALESCE(SUM(quantity * unit_price), 0) "
            "FROM dbo.order_items WHERE order_id = %s), "
            "updated_at = SYSUTCDATETIME() WHERE order_id = %s",
            (order_id, order_id),
        )
    return count, item_count


def delete_order_items(cur, count: int) -> int:
    cur.execute(
        "SELECT TOP (%s) order_id FROM dbo.order_items "
        "GROUP BY order_id ORDER BY NEWID()",
        (count,),
    )
    order_ids = [row[0] for row in cur.fetchall()]
    for order_id in order_ids:
        cur.execute(
            "SELECT TOP (1) order_item_id FROM dbo.order_items "
            "WHERE order_id = %s ORDER BY NEWID()",
            (order_id,),
        )
        item_id = cur.fetchone()[0]
        cur.execute("DELETE FROM dbo.order_items WHERE order_item_id = %s", (item_id,))
        cur.execute(
            "UPDATE dbo.orders SET total_amount = "
            "(SELECT COALESCE(SUM(quantity * unit_price), 0) "
            "FROM dbo.order_items WHERE order_id = %s), "
            "updated_at = SYSUTCDATETIME() WHERE order_id = %s",
            (order_id, order_id),
        )
    return len(order_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", type=int, default=5, help="số khách hàng bị sửa thành phố")
    parser.add_argument("--insert", type=int, default=3, help="số khách hàng thêm mới")
    parser.add_argument(
        "--order-update",
        type=non_negative_int,
        default=0,
        help="số đơn NEW chuyển lần lượt qua PAID, SHIPPED, COMPLETED",
    )
    parser.add_argument(
        "--order-insert",
        type=non_negative_int,
        default=0,
        help="số đơn mới cần thêm, mỗi đơn có 1-3 dòng chi tiết",
    )
    parser.add_argument(
        "--item-delete",
        type=non_negative_int,
        default=0,
        help="số đơn cần xóa cứng một dòng chi tiết",
    )
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

    try:
        with conn:
            cur = conn.cursor()

            cur.execute(
                "SELECT TOP (%s) customer_id FROM dbo.customers ORDER BY NEWID()",
                (args.update,),
            )
            customer_ids = [row[0] for row in cur.fetchall()]
            for customer_id in customer_ids:
                cur.execute(
                    "UPDATE dbo.customers SET city = %s WHERE customer_id = %s",
                    (random.choice(CITIES), customer_id),
                )

            for _ in range(args.insert):
                cur.execute(
                    "INSERT INTO dbo.customers (full_name, email, city) "
                    "VALUES (%s, %s, %s)",
                    (
                        fake.name(),
                        f"moi_{uuid.uuid4().hex[:10]}@example.com",
                        random.choice(CITIES),
                    ),
                )

            updated_orders = update_orders(cur, args.order_update)
            inserted_orders, inserted_items = insert_orders(cur, args.order_insert)
            deleted_orders = delete_order_items(cur, args.item_delete)
            conn.commit()
    except (pymssql.Error, ValueError) as exc:
        print(f"Không thể giả lập thay đổi: {exc}")
        return 1

    print(f"Đã sửa {len(customer_ids)} khách hàng: {customer_ids}")
    print(f"Đã thêm {args.insert} khách hàng mới")
    print(f"Đã chuyển trạng thái {updated_orders}/{args.order_update} đơn NEW")
    print(
        f"Đã thêm {inserted_orders} đơn hàng mới và "
        f"{inserted_items} dòng chi tiết"
    )
    print(f"Đã xóa một dòng chi tiết của {deleted_orders}/{args.item_delete} đơn hàng")
    return 0


if __name__ == "__main__":
    sys.exit(main())
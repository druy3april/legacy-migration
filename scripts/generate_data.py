"""Sinh dữ liệu giả cho hệ thống cũ: khách hàng và sản phẩm."""
import os
import random
import sys
from datetime import datetime, timedelta
import pymssql
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

SEED = 42            # cố định để mỗi lần sinh ra cùng một bộ dữ liệu
NUM_CUSTOMERS = 2000

CITIES = ["Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ", "Huế", "Nha Trang", "Bắc Ninh"]

# danh mục -> (danh sách loại hàng, giá thấp nhất, giá cao nhất)
CATALOG = {
    "Điện tử": (["Điện thoại", "Máy tính bảng", "Tai nghe", "Loa bluetooth"], 500_000, 25_000_000),
    "Gia dụng": (["Nồi cơm điện", "Máy xay sinh tố", "Ấm đun nước", "Quạt điện"], 200_000, 4_000_000),
    "Thời trang": (["Áo thun", "Quần jeans", "Áo khoác", "Giày thể thao"], 100_000, 1_500_000),
    "Mỹ phẩm": (["Kem dưỡng da", "Sữa rửa mặt", "Son môi", "Nước hoa"], 80_000, 2_000_000),
    "Thực phẩm": (["Cà phê", "Trà", "Bánh kẹo", "Mì ăn liền"], 20_000, 400_000),
}
VARIANTS = ["Loại 1", "Loại 2", "Loại 3"]

NUM_ORDERS = 20000
ORDER_START = datetime(2026, 4, 1)   # ngày bắt đầu của dữ liệu đơn hàng
ORDER_DAYS = 180                      # trải đơn hàng trong 180 ngày
STATUS_WEIGHTS = {"COMPLETED": 60, "SHIPPED": 10, "PAID": 10, "NEW": 5, "CANCELLED": 15}

def get_connection():
    return pymssql.connect(
        server=os.getenv("MSSQL_HOST", "localhost"),
        port=int(os.getenv("MSSQL_PORT", "1433")),
        user="sa",
        password=os.environ["MSSQL_SA_PASSWORD"],
        database=os.getenv("MSSQL_DATABASE", "LegacyRetail"),
        login_timeout=10,
    )


def table_has_data(cur, table: str) -> bool:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0] > 0


def seed_customers(conn, fake: Faker) -> None:
    cur = conn.cursor()
    if table_has_data(cur, "dbo.customers"):
        print("customers đã có dữ liệu, bỏ qua")
        return

    rows = []
    for i in range(1, NUM_CUSTOMERS + 1):
        city = random.choice(CITIES) if random.random() > 0.1 else None  # ~10% để trống
        rows.append((fake.name(), f"khach{i:05d}@example.com", city))

    cur.executemany(
        "INSERT INTO dbo.customers (full_name, email, city) VALUES (%s, %s, %s)",
        rows,
    )
    conn.commit()
    print(f"Đã thêm {len(rows)} khách hàng")


def seed_products(conn) -> None:
    cur = conn.cursor()
    if table_has_data(cur, "dbo.products"):
        print("products đã có dữ liệu, bỏ qua")
        return

    rows = []
    for category, (items, low, high) in CATALOG.items():
        for item in items:
            for variant in VARIANTS:
                price = int(round(random.uniform(low, high), -3))  # làm tròn đến nghìn đồng
                is_active = 0 if random.random() < 0.05 else 1      # ~5% ngừng bán
                rows.append((f"{item} {variant}", category, price, is_active))

    cur.executemany(
        "INSERT INTO dbo.products (product_name, category, unit_price, is_active) VALUES (%s, %s, %s, %s)",
        rows,
    )
    conn.commit()
    print(f"Đã thêm {len(rows)} sản phẩm")


def seed_orders(conn) -> None:
    cur = conn.cursor()
    if table_has_data(cur, "dbo.orders"):
        print("orders đã có dữ liệu, bỏ qua")
        return

    cur.execute("SELECT customer_id FROM dbo.customers")
    customer_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT product_id, unit_price FROM dbo.products WHERE is_active = 1")
    products = cur.fetchall()
    if not customer_ids or not products:
        print("Chưa có khách hàng hoặc sản phẩm, hãy sinh chúng trước")
        return

    random.seed(SEED + 1)  # tách riêng hạt giống để đơn hàng luôn giống nhau mỗi lần
    statuses = list(STATUS_WEIGHTS)
    weights = list(STATUS_WEIGHTS.values())

    orders = []  # mỗi phần tử: (customer_id, order_date, status, total_amount, updated_at)
    lines_per_order = []  # song song với orders: danh sách dòng hàng của từng đơn
    for _ in range(NUM_ORDERS):
        order_date = ORDER_START + timedelta(
            days=random.randrange(ORDER_DAYS), seconds=random.randrange(86400)
        )
        status = random.choices(statuses, weights)[0]

        lines = []
        for product_id, unit_price in random.sample(products, random.randint(1, 5)):
            lines.append((product_id, random.randint(1, 4), unit_price))
        total = sum(qty * price for _, qty, price in lines)

        updated_at = order_date + timedelta(hours=random.randint(0, 48))
        orders.append((random.choice(customer_ids), order_date, status, total, updated_at))
        lines_per_order.append(lines)

    cur.executemany(
        "INSERT INTO dbo.orders (customer_id, order_date, status, total_amount, updated_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        orders,
    )
    cur.execute("SELECT order_id FROM dbo.orders ORDER BY order_id")
    order_ids = [row[0] for row in cur.fetchall()]

    item_rows = []
    for order_id, lines in zip(order_ids, lines_per_order):
        for product_id, qty, price in lines:
            item_rows.append((order_id, product_id, qty, price))

    cur.executemany(
        "INSERT INTO dbo.order_items (order_id, product_id, quantity, unit_price) "
        "VALUES (%s, %s, %s, %s)",
        item_rows,
    )
    conn.commit()
    print(f"Đã thêm {len(orders)} đơn hàng và {len(item_rows)} dòng chi tiết")

def main() -> int:
    random.seed(SEED)
    Faker.seed(SEED)
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
        seed_customers(conn, fake)
        seed_products(conn)
        seed_orders(conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""Sinh dữ liệu giả cho hệ thống cũ: khách hàng và sản phẩm."""
import os
import random
import sys

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
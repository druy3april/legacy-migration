"""Source schema contract: type, length, precision/scale, nullability."""

CONTRACT = {
    "customers": {
        "customer_id": ("int", None, 10, 0, "NO"),
        "full_name": ("nvarchar", 100, None, None, "NO"),
        "email": ("varchar", 150, None, None, "NO"),
        "city": ("nvarchar", 50, None, None, "YES"),
        "created_at": ("datetime2", None, None, None, "NO"),
    },
    "products": {
        "product_id": ("int", None, 10, 0, "NO"),
        "product_name": ("nvarchar", 150, None, None, "NO"),
        "category": ("nvarchar", 50, None, None, "NO"),
        "unit_price": ("decimal", None, 12, 2, "NO"),
        "is_active": ("bit", None, None, None, "NO"),
        "created_at": ("datetime2", None, None, None, "NO"),
    },
    "orders": {
        "order_id": ("int", None, 10, 0, "NO"),
        "customer_id": ("int", None, 10, 0, "NO"),
        "order_date": ("datetime2", None, None, None, "NO"),
        "status": ("varchar", 20, None, None, "NO"),
        "total_amount": ("decimal", None, 14, 2, "NO"),
        "updated_at": ("datetime2", None, None, None, "NO"),
    },
    "order_items": {
        "order_item_id": ("int", None, 10, 0, "NO"),
        "order_id": ("int", None, 10, 0, "NO"),
        "product_id": ("int", None, 10, 0, "NO"),
        "quantity": ("int", None, 10, 0, "NO"),
        "unit_price": ("decimal", None, 12, 2, "NO"),
    },
}


def schema_differences(rows, table):
    actual = {}
    issues = []
    for name, dtype, length, precision, scale, nullable, datetime_precision in rows:
        if dtype not in {"int", "decimal", "numeric"}:
            precision, scale = None, None
        actual[name] = (dtype, length, precision, scale, nullable)
        if dtype == "datetime2" and datetime_precision != 0:
            issues.append(f"{name}: datetime precision {datetime_precision}, expected 0")
    expected = dict(CONTRACT[table], row_ver=("timestamp", None, None, None, "NO"))
    for name in sorted(set(actual) | set(expected)):
        if actual.get(name) != expected.get(name):
            issues.append(f"{name}: actual={actual.get(name)}, expected={expected.get(name)}")
    return issues

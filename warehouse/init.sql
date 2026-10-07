-- Schema chứa dữ liệu thô tải từ hệ thống cũ, và schema chứa bảng điều khiển ETL
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS etl;

-- Mỗi bảng nguồn một dòng: lần trước đã tải đến rowversion nào
CREATE TABLE IF NOT EXISTS etl.watermarks (
    table_name       TEXT        PRIMARY KEY,
    last_rowversion  BIGINT      NOT NULL DEFAULT 0,
    last_run_at      TIMESTAMPTZ
);

INSERT INTO etl.watermarks (table_name)
VALUES ('customers'), ('products'), ('orders'), ('order_items')
ON CONFLICT (table_name) DO NOTHING;

-- Bảng thô: giữ nguyên dữ liệu nguồn. Giờ trong created_at là UTC (chưa gắn múi giờ)
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id  INT         PRIMARY KEY,
    full_name    TEXT        NOT NULL,
    email        TEXT        NOT NULL,
    city         TEXT,
    created_at   TIMESTAMP   NOT NULL,
    row_ver      BIGINT      NOT NULL,
    _loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bảng thô cho sản phẩm. Giữ nguyên dữ liệu nguồn, chỉ có khóa chính (không có CHECK, không có khóa ngoại)
CREATE TABLE IF NOT EXISTS raw.products (
    product_id    INT           PRIMARY KEY,
    product_name  TEXT          NOT NULL,
    category      TEXT          NOT NULL,
    unit_price    NUMERIC(12,2) NOT NULL,
    is_active     BOOLEAN       NOT NULL,
    created_at    TIMESTAMP     NOT NULL,
    row_ver       BIGINT        NOT NULL,
    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id      INT           PRIMARY KEY,
    customer_id   INT           NOT NULL,
    order_date    TIMESTAMP     NOT NULL,
    status        TEXT          NOT NULL,
    total_amount  NUMERIC(14,2) NOT NULL,
    updated_at    TIMESTAMP     NOT NULL,
    row_ver       BIGINT        NOT NULL,
    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_item_id INT           PRIMARY KEY,
    order_id      INT           NOT NULL,
    product_id    INT           NOT NULL,
    quantity      INT           NOT NULL,
    unit_price    NUMERIC(12,2) NOT NULL,
    row_ver       BIGINT        NOT NULL,
    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);


-- Vai trò và database riêng để Airflow lưu metadata (lab cục bộ nên dùng mật khẩu đơn giản)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow') THEN
        CREATE ROLE airflow LOGIN PASSWORD 'airflow';
    END IF;
END
$$;

SELECT 'CREATE DATABASE airflow OWNER airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
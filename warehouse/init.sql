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
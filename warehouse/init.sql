-- Schema chứa dữ liệu thô tải từ hệ thống cũ, và schema chứa bảng điều khiển ETL
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS etl;

-- Mỗi bảng nguồn một dòng: lần trước đã tải đến rowversion nào
CREATE TABLE IF NOT EXISTS etl.watermarks (
    table_name       TEXT        PRIMARY KEY,
    last_rowversion  BIGINT      NOT NULL DEFAULT 0,
    last_run_at      TIMESTAMPTZ
);

DO $$
BEGIN
    IF to_regclass('etl.ingest_log') IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
              AND column_name = 'ingest_id'
        ) THEN
            ALTER TABLE etl.ingest_log RENAME COLUMN ingest_id TO id;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
              AND column_name = 'last_rowversion'
        ) THEN
            ALTER TABLE etl.ingest_log RENAME COLUMN last_rowversion TO from_rowversion;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
              AND column_name = 'upper_rowversion'
        ) THEN
            ALTER TABLE etl.ingest_log RENAME COLUMN upper_rowversion TO to_rowversion;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
              AND column_name = 'rows_loaded'
        ) THEN
            ALTER TABLE etl.ingest_log RENAME COLUMN rows_loaded TO row_count;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
              AND column_name = 'logged_at'
        ) THEN
            ALTER TABLE etl.ingest_log RENAME COLUMN logged_at TO loaded_at;
        END IF;
        ALTER TABLE etl.ingest_log ADD COLUMN IF NOT EXISTS object_key TEXT;
        ALTER TABLE etl.ingest_log ALTER COLUMN row_count TYPE INT USING row_count::INT;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS etl.ingest_log (
    id               BIGSERIAL   PRIMARY KEY,
    run_id           TEXT        NOT NULL,
    table_name       TEXT        NOT NULL,
    from_rowversion  BIGINT      NOT NULL,
    to_rowversion    BIGINT      NOT NULL,
    row_count        INT         NOT NULL,
    object_key       TEXT,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ingest_log_run_table
    ON etl.ingest_log (run_id, table_name);

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
    _loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    _deleted_at  TIMESTAMPTZ
);
ALTER TABLE raw.customers ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;

-- Bảng thô cho sản phẩm. Giữ nguyên dữ liệu nguồn, chỉ có khóa chính (không có CHECK, không có khóa ngoại)
CREATE TABLE IF NOT EXISTS raw.products (
    product_id    INT           PRIMARY KEY,
    product_name  TEXT          NOT NULL,
    category      TEXT          NOT NULL,
    unit_price    NUMERIC(12,2) NOT NULL,
    is_active     BOOLEAN       NOT NULL,
    created_at    TIMESTAMP     NOT NULL,
    row_ver       BIGINT        NOT NULL,
    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    _deleted_at   TIMESTAMPTZ
);
ALTER TABLE raw.products ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id      INT           PRIMARY KEY,
    customer_id   INT           NOT NULL,
    order_date    TIMESTAMP     NOT NULL,
    status        TEXT          NOT NULL,
    total_amount  NUMERIC(14,2) NOT NULL,
    updated_at    TIMESTAMP     NOT NULL,
    row_ver       BIGINT        NOT NULL,
    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    _deleted_at   TIMESTAMPTZ
);
ALTER TABLE raw.orders ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_item_id INT           PRIMARY KEY,
    order_id      INT           NOT NULL,
    product_id    INT           NOT NULL,
    quantity      INT           NOT NULL,
    unit_price    NUMERIC(12,2) NOT NULL,
    row_ver       BIGINT        NOT NULL,
    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    _deleted_at   TIMESTAMPTZ
);
ALTER TABLE raw.order_items ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;


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

-- =====================================================================
-- Tuần 5: đối soát (reconciliation)
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS recon;

-- Mỗi lần chạy job ban đêm cũ: snapshot nguồn trước/sau khi chạy
CREATE TABLE IF NOT EXISTS recon.legacy_batches (
    batch_id            TEXT        PRIMARY KEY,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ NOT NULL,
    fingerprint_before  JSONB       NOT NULL,
    fingerprint_after   JSONB       NOT NULL,
    stable              BOOLEAN     NOT NULL
);

-- Mỗi dòng = một phép kiểm tra của một báo cáo trong một lần đối soát
CREATE TABLE IF NOT EXISTS recon.results (
    id               BIGSERIAL   PRIMARY KEY,
    run_id           TEXT        NOT NULL,
    legacy_batch_id  TEXT,
    checked_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    report           TEXT        NOT NULL,
    check_level      TEXT        NOT NULL,   -- L0_snapshot, L1_row_count ... L5_checksum
    check_name       TEXT        NOT NULL,
    legacy_value     TEXT,
    new_value        TEXT,
    diff_count       INT         NOT NULL DEFAULT 0,
    tolerance        NUMERIC,
    status           TEXT        NOT NULL CHECK (status IN ('PASS', 'WARN', 'FAIL', 'SKIP')),
    details          JSONB
);
CREATE INDEX IF NOT EXISTS ix_recon_results_run ON recon.results (run_id, report);
CREATE INDEX IF NOT EXISTS ix_recon_results_checked ON recon.results (checked_at);

-- Mẫu dòng lệch (tối đa 200 dòng mỗi báo cáo mỗi lần chạy) để điều tra
CREATE TABLE IF NOT EXISTS recon.row_diffs (
    id            BIGSERIAL   PRIMARY KEY,
    run_id        TEXT        NOT NULL,
    report        TEXT        NOT NULL,
    key           JSONB       NOT NULL,
    diff_type     TEXT        NOT NULL,  -- only_in_legacy, only_in_new, value, tie, duplicate_key
    column_name   TEXT,
    legacy_value  TEXT,
    new_value     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_recon_row_diffs_run ON recon.row_diffs (run_id, report);

-- Trạng thái gộp mỗi báo cáo mỗi lần chạy: lấy trạng thái xấu nhất
CREATE OR REPLACE VIEW recon.v_report_status AS
SELECT
    run_id,
    report,
    min(checked_at)                                            AS checked_at,
    (min(checked_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date    AS run_date,
    CASE max(CASE status WHEN 'FAIL' THEN 3 WHEN 'SKIP' THEN 2 WHEN 'WARN' THEN 1 ELSE 0 END)
        WHEN 3 THEN 'FAIL' WHEN 2 THEN 'SKIP' WHEN 1 THEN 'WARN' ELSE 'PASS'
    END                                                        AS status,
    coalesce(sum(diff_count) FILTER (WHERE check_level = 'L4_row'), 0) AS diff_rows,
    count(*) FILTER (WHERE status = 'FAIL')                    AS failed_checks
FROM recon.results
GROUP BY run_id, report;

-- Mỗi ngày (giờ VN) lấy lần chạy cuối cùng của từng báo cáo
CREATE OR REPLACE VIEW recon.v_daily_status AS
SELECT DISTINCT ON (run_date, report)
    run_date, report, status, diff_rows, failed_checks, run_id, checked_at
FROM recon.v_report_status
ORDER BY run_date, report, checked_at DESC;

-- Lần chạy gần nhất, chi tiết từng phép kiểm tra
CREATE OR REPLACE VIEW recon.v_latest_run AS
SELECT r.*
FROM recon.results AS r
WHERE r.run_id = (SELECT run_id FROM recon.results ORDER BY checked_at DESC LIMIT 1);

-- Metabase: database riêng cho metadata, và một user chỉ-đọc vào warehouse
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'metabase') THEN
        CREATE ROLE metabase LOGIN PASSWORD 'metabase';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bi_reader') THEN
        CREATE ROLE bi_reader LOGIN PASSWORD 'bi_reader';
    END IF;
END
$$;

SELECT 'CREATE DATABASE metabase OWNER metabase'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'metabase')\gexec

CREATE SCHEMA IF NOT EXISTS marts;
GRANT USAGE ON SCHEMA recon, marts TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA recon, marts TO bi_reader;
-- dbt tạo lại bảng mart mỗi lần build => cấp quyền mặc định cho bảng tạo sau này
ALTER DEFAULT PRIVILEGES IN SCHEMA recon, marts GRANT SELECT ON TABLES TO bi_reader;
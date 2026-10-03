USE LegacyRetail;
GO

-- Bảng khách hàng
IF OBJECT_ID(N'dbo.customers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customers (
        customer_id  INT IDENTITY(1,1) NOT NULL,
        full_name    NVARCHAR(100)     NOT NULL,
        email        VARCHAR(150)      NOT NULL,
        city         NVARCHAR(50)      NULL,
        created_at   DATETIME2(0)      NOT NULL CONSTRAINT DF_customers_created_at DEFAULT SYSUTCDATETIME(),
        row_ver      ROWVERSION        NOT NULL,
        CONSTRAINT PK_customers PRIMARY KEY (customer_id),
        CONSTRAINT UQ_customers_email UNIQUE (email)
    );
END
GO

-- Bảng sản phẩm
IF OBJECT_ID(N'dbo.products', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.products (
        product_id    INT IDENTITY(1,1) NOT NULL,
        product_name  NVARCHAR(150)     NOT NULL,
        category      NVARCHAR(50)      NOT NULL,
        unit_price    DECIMAL(12,2)     NOT NULL CONSTRAINT CK_products_price CHECK (unit_price >= 0),
        is_active     BIT               NOT NULL CONSTRAINT DF_products_is_active DEFAULT 1,
        created_at    DATETIME2(0)      NOT NULL CONSTRAINT DF_products_created_at DEFAULT SYSUTCDATETIME(),
        row_ver       ROWVERSION        NOT NULL,
        CONSTRAINT PK_products PRIMARY KEY (product_id)
    );
END
GO

-- Bảng đơn hàng
IF OBJECT_ID(N'dbo.orders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.orders (
        order_id      INT IDENTITY(1,1) NOT NULL,
        customer_id   INT               NOT NULL,
        order_date    DATETIME2(0)      NOT NULL,
        status        VARCHAR(20)       NOT NULL,
        total_amount  DECIMAL(14,2)     NOT NULL CONSTRAINT DF_orders_total DEFAULT 0,
        updated_at    DATETIME2(0)      NOT NULL CONSTRAINT DF_orders_updated_at DEFAULT SYSUTCDATETIME(),
        row_ver       ROWVERSION        NOT NULL,
        CONSTRAINT PK_orders PRIMARY KEY (order_id),
        CONSTRAINT FK_orders_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers (customer_id),
        CONSTRAINT CK_orders_status CHECK (status IN ('NEW','PAID','SHIPPED','COMPLETED','CANCELLED'))
    );

    CREATE INDEX IX_orders_customer_id ON dbo.orders (customer_id);
    CREATE INDEX IX_orders_order_date  ON dbo.orders (order_date);
END
GO

-- Bảng chi tiết đơn hàng
IF OBJECT_ID(N'dbo.order_items', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.order_items (
        order_item_id INT IDENTITY(1,1) NOT NULL,
        order_id      INT               NOT NULL,
        product_id    INT               NOT NULL,
        quantity      INT               NOT NULL CONSTRAINT CK_items_quantity CHECK (quantity > 0),
        unit_price    DECIMAL(12,2)     NOT NULL CONSTRAINT CK_items_price CHECK (unit_price >= 0),
        row_ver       ROWVERSION        NOT NULL,
        CONSTRAINT PK_order_items PRIMARY KEY (order_item_id),
        CONSTRAINT FK_items_order FOREIGN KEY (order_id) REFERENCES dbo.orders (order_id),
        CONSTRAINT FK_items_product FOREIGN KEY (product_id) REFERENCES dbo.products (product_id)
    );

    CREATE INDEX IX_items_order_id ON dbo.order_items (order_id);
END
GO

-- Bảng báo cáo: doanh thu theo ngày
IF OBJECT_ID(N'dbo.daily_revenue', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.daily_revenue (
        revenue_date   DATE          NOT NULL,
        order_count    INT           NOT NULL,
        gross_revenue  DECIMAL(18,2) NOT NULL,
        refreshed_at   DATETIME2(0)  NOT NULL CONSTRAINT DF_daily_revenue_refreshed DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_daily_revenue PRIMARY KEY (revenue_date)
    );
END
GO

-- Bảng báo cáo: giá trị vòng đời của khách hàng (LTV)
IF OBJECT_ID(N'dbo.customer_ltv', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_ltv (
        customer_id       INT           NOT NULL,
        order_count       INT           NOT NULL,
        total_spent       DECIMAL(18,2) NOT NULL,
        first_order_date  DATE          NULL,
        last_order_date   DATE          NULL,
        refreshed_at      DATETIME2(0)  NOT NULL CONSTRAINT DF_customer_ltv_refreshed DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_customer_ltv PRIMARY KEY (customer_id)
    );
END
GO

-- Bảng báo cáo: phân khúc khách hàng
IF OBJECT_ID(N'dbo.customer_segments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_segments (
        customer_id   INT          NOT NULL,
        segment       VARCHAR(20)  NOT NULL,
        refreshed_at  DATETIME2(0) NOT NULL CONSTRAINT DF_customer_segments_refreshed DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_customer_segments PRIMARY KEY (customer_id)
    );
END
GO
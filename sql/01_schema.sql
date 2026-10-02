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
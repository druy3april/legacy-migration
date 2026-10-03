USE LegacyRetail;
GO

-- Làm mới doanh thu theo ngày (không tính đơn đã hủy)
CREATE OR ALTER PROCEDURE dbo.sp_refresh_daily_revenue
AS
BEGIN
    SET NOCOUNT ON;

    TRUNCATE TABLE dbo.daily_revenue;

    INSERT INTO dbo.daily_revenue (revenue_date, order_count, gross_revenue)
    SELECT CAST(order_date AS DATE),
           COUNT(*),
           SUM(total_amount)
    FROM dbo.orders
    WHERE status <> 'CANCELLED'
    GROUP BY CAST(order_date AS DATE);
END
GO

-- Làm mới giá trị vòng đời khách hàng (LTV), viết kiểu bảng tạm nhiều tầng
CREATE OR ALTER PROCEDURE dbo.sp_refresh_customer_ltv
AS
BEGIN
    SET NOCOUNT ON;

    -- Tầng 1: gom đơn đã thanh toán trở lên theo từng khách
    SELECT customer_id,
           COUNT(*)          AS order_count,
           SUM(total_amount) AS total_spent,
           MIN(order_date)   AS first_order,
           MAX(order_date)   AS last_order
    INTO #order_totals
    FROM dbo.orders
    WHERE status IN ('PAID', 'SHIPPED', 'COMPLETED')
    GROUP BY customer_id;

    -- Tầng 2: nối với toàn bộ khách; khách chưa mua gì thì ISNULL về 0
    SELECT c.customer_id,
           ISNULL(t.order_count, 0) AS order_count,
           ISNULL(t.total_spent, 0) AS total_spent,
           CONVERT(DATE, t.first_order) AS first_order_date,
           CONVERT(DATE, t.last_order)  AS last_order_date
    INTO #ltv_all
    FROM dbo.customers c
    LEFT JOIN #order_totals t ON t.customer_id = c.customer_id;

    -- Tầng 3: xóa bảng cũ rồi nạp lại
    TRUNCATE TABLE dbo.customer_ltv;

    INSERT INTO dbo.customer_ltv (customer_id, order_count, total_spent, first_order_date, last_order_date)
    SELECT customer_id, order_count, total_spent, first_order_date, last_order_date
    FROM #ltv_all;

    DROP TABLE #order_totals;
    DROP TABLE #ltv_all;
END
GO

-- Phân khúc khách hàng, viết kiểu CURSOR duyệt từng dòng
CREATE OR ALTER PROCEDURE dbo.sp_refresh_customer_segments
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @as_of DATE = '2026-09-30';  -- ngày chốt số liệu, cố định để kết quả không đổi theo ngày chạy
    DECLARE @customer_id INT;
    DECLARE @order_count INT;
    DECLARE @total_spent DECIMAL(18,2);
    DECLARE @last_order  DATE;
    DECLARE @segment     VARCHAR(20);

    TRUNCATE TABLE dbo.customer_segments;

    DECLARE cur_customers CURSOR LOCAL FAST_FORWARD FOR
        SELECT customer_id, order_count, total_spent, last_order_date
        FROM dbo.customer_ltv;

    OPEN cur_customers;
    FETCH NEXT FROM cur_customers INTO @customer_id, @order_count, @total_spent, @last_order;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF @order_count = 0
            SET @segment = 'INACTIVE';
        ELSE IF DATEDIFF(DAY, @last_order, @as_of) > 60
            SET @segment = 'DORMANT';
        ELSE IF @total_spent >= 250000000
            SET @segment = 'VIP';
        ELSE IF @total_spent >= 100000000
            SET @segment = 'REGULAR';
        ELSE
            SET @segment = 'CASUAL';

        INSERT INTO dbo.customer_segments (customer_id, segment)
        VALUES (@customer_id, @segment);

        FETCH NEXT FROM cur_customers INTO @customer_id, @order_count, @total_spent, @last_order;
    END

    CLOSE cur_customers;
    DEALLOCATE cur_customers;
END
GO

-- Làm mới doanh số theo sản phẩm: biến bảng + MERGE (upsert)
CREATE OR ALTER PROCEDURE dbo.sp_refresh_product_sales
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @sales TABLE (
        product_id  INT           NOT NULL PRIMARY KEY,
        units_sold  INT           NOT NULL,
        revenue     DECIMAL(18,2) NOT NULL,
        last_sold   DATE          NULL
    );

    INSERT INTO @sales (product_id, units_sold, revenue, last_sold)
    SELECT oi.product_id,
           SUM(oi.quantity),
           SUM(oi.quantity * oi.unit_price),
           CONVERT(DATE, MAX(o.order_date))
    FROM dbo.order_items oi
    JOIN dbo.orders o ON o.order_id = oi.order_id
    WHERE o.status IN ('PAID', 'SHIPPED', 'COMPLETED')
    GROUP BY oi.product_id;

    MERGE dbo.product_sales AS tgt
    USING @sales AS src
        ON tgt.product_id = src.product_id
    WHEN MATCHED THEN
        UPDATE SET tgt.units_sold     = src.units_sold,
                   tgt.revenue        = src.revenue,
                   tgt.last_sold_date = src.last_sold,
                   tgt.refreshed_at   = SYSUTCDATETIME()
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (product_id, units_sold, revenue, last_sold_date)
        VALUES (src.product_id, src.units_sold, src.revenue, src.last_sold)
    WHEN NOT MATCHED BY SOURCE THEN
        DELETE;
END
GO

-- Doanh thu theo danh mục x tháng, dùng SQL động để tạo cột theo tháng có dữ liệu
CREATE OR ALTER PROCEDURE dbo.sp_refresh_category_monthly_revenue
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @cols NVARCHAR(MAX);
    DECLARE @sql  NVARCHAR(MAX);

    -- Danh sách tháng có đơn hàng, dạng: [2026-04],[2026-05],...
    SELECT @cols = STRING_AGG(QUOTENAME(ym), ',') WITHIN GROUP (ORDER BY ym)
    FROM (SELECT DISTINCT CONVERT(CHAR(7), order_date, 126) AS ym FROM dbo.orders) AS m;

    IF @cols IS NULL
        RETURN;

    -- Số cột thay đổi theo dữ liệu nên bảng đích phải xóa đi tạo lại
    IF OBJECT_ID(N'dbo.category_monthly_revenue', N'U') IS NOT NULL
        DROP TABLE dbo.category_monthly_revenue;

    SET @sql = N'
        SELECT category, ' + @cols + N'
        INTO dbo.category_monthly_revenue
        FROM (
            SELECT p.category,
                   CONVERT(CHAR(7), o.order_date, 126) AS ym,
                   oi.quantity * oi.unit_price AS amount
            FROM dbo.order_items oi
            JOIN dbo.orders   o ON o.order_id   = oi.order_id
            JOIN dbo.products p ON p.product_id = oi.product_id
            WHERE o.status IN (''PAID'', ''SHIPPED'', ''COMPLETED'')
        ) AS src
        PIVOT (SUM(amount) FOR ym IN (' + @cols + N')) AS pvt;';

    EXEC (@sql);
END
GO

-- Doanh thu lũy kế theo ngày, viết kiểu vòng lặp WHILE đi từng ngày
CREATE OR ALTER PROCEDURE dbo.sp_refresh_cumulative_revenue
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @day     DATE;
    DECLARE @last    DATE;
    DECLARE @daily   DECIMAL(18,2);
    DECLARE @running DECIMAL(18,2) = 0;

    SELECT @day = MIN(revenue_date), @last = MAX(revenue_date)
    FROM dbo.daily_revenue;

    TRUNCATE TABLE dbo.cumulative_revenue;

    WHILE @day IS NOT NULL AND @day <= @last
    BEGIN
        SELECT @daily = ISNULL(SUM(gross_revenue), 0)
        FROM dbo.daily_revenue
        WHERE revenue_date = @day;

        SET @running = @running + @daily;

        INSERT INTO dbo.cumulative_revenue (revenue_date, daily_revenue, running_total)
        VALUES (@day, @daily, @running);

        SET @day = DATEADD(DAY, 1, @day);
    END
END
GO

-- Điều phối job ban đêm: chạy 3 procedure theo đúng thứ tự phụ thuộc
CREATE OR ALTER PROCEDURE dbo.sp_run_nightly_batch
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @started DATETIME2(0) = SYSUTCDATETIME();

    EXEC dbo.sp_refresh_daily_revenue;
    EXEC dbo.sp_refresh_customer_ltv;
    EXEC dbo.sp_refresh_customer_segments;
    EXEC dbo.sp_refresh_product_sales;
    EXEC dbo.sp_refresh_category_monthly_revenue;
    EXEC dbo.sp_refresh_cumulative_revenue;

    PRINT CONCAT('Batch hoan tat sau ', DATEDIFF(SECOND, @started, SYSUTCDATETIME()), ' giay');
END
GO


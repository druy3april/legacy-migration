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
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

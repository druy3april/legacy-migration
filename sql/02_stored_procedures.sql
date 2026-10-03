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

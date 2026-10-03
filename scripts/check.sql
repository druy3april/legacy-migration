SET NOCOUNT ON;

PRINT '=== Doanh thu 7 ngay gan nhat ===';
SELECT TOP 7 revenue_date, order_count, gross_revenue
FROM dbo.daily_revenue
ORDER BY revenue_date DESC;

PRINT '';
PRINT '=== Phan bo phan khuc khach hang ===';
SELECT segment, COUNT(*) AS so_khach
FROM dbo.customer_segments
GROUP BY segment
ORDER BY so_khach DESC;

PRINT '';
PRINT '=== So dong cac bang ===';
SELECT 'customers' AS bang, COUNT(*) AS so_dong FROM dbo.customers
UNION ALL SELECT 'products', COUNT(*) FROM dbo.products
UNION ALL SELECT 'orders', COUNT(*) FROM dbo.orders
UNION ALL SELECT 'order_items', COUNT(*) FROM dbo.order_items;
GO
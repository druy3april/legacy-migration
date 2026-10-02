-- Tạo database của hệ thống bán lẻ "cũ". Chạy lại nhiều lần vẫn an toàn.
IF DB_ID(N'LegacyRetail') IS NULL
BEGIN
    CREATE DATABASE LegacyRetail;
    PRINT 'Da tao database LegacyRetail';
END
ELSE
    PRINT 'Database LegacyRetail da ton tai';
GO

-- Môi trường dev không cần sao lưu log giao dịch, dùng SIMPLE để log không phình to
ALTER DATABASE LegacyRetail SET RECOVERY SIMPLE;
GO
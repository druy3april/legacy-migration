BEGIN TRANSACTION;
UPDATE dbo.customers
SET city = CASE WHEN city = N'Thu nghiem A' THEN N'Thu nghiem B' ELSE N'Thu nghiem A' END
WHERE customer_id = 1002;
WAITFOR DELAY '00:02:00';
COMMIT TRANSACTION;
GO
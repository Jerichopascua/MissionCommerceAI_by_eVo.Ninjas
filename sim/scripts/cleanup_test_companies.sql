/*
Remove the throwaway test companies from the development database (PesoWeb_MissionDev). TEST BENCH ONLY: never run this on a real database.

A company is removed only if EVERY one of its users has an address ending in .test, none ends in @simworld.test (the simulated AI worlds are kept),
its TenantID is above 10 (the first ten companies are never touched), and none of its users is the snapshot operator.

    sqlcmd -S "(localdb)\MSSQLLocalDB" -d PesoWeb_MissionDev -E -b -v Apply=0 -i scripts\cleanup_test_companies.sql     (preview: counts only)
    sqlcmd -S "(localdb)\MSSQLLocalDB" -d PesoWeb_MissionDev -E -b -v Apply=1 -i scripts\cleanup_test_companies.sql     (delete)

Take a backup first (on a drive with room). The delete runs in one transaction: if any row of a removed company is left after the retries,
everything is rolled back.
*/
SET NOCOUNT ON;
SET XACT_ABORT OFF;

IF OBJECT_ID('tempdb..#victims') IS NOT NULL DROP TABLE #victims;
SELECT u.TenantID INTO #victims
FROM Users u
GROUP BY u.TenantID
HAVING u.TenantID > 10
   AND SUM(CASE WHEN u.Email NOT LIKE '%.test' THEN 1 ELSE 0 END) = 0
   AND SUM(CASE WHEN u.Email LIKE '%@simworld.test' THEN 1 ELSE 0 END) = 0
   AND SUM(CASE WHEN u.Email = 'snapadmin@snap.test' THEN 1 ELSE 0 END) = 0;

DECLARE @remove int = (SELECT COUNT(*) FROM #victims);
DECLARE @kept int = (SELECT COUNT(DISTINCT TenantID) FROM Users WHERE TenantID NOT IN (SELECT TenantID FROM #victims));
PRINT 'Companies to remove: ' + CAST(@remove AS varchar(10));
PRINT 'Companies kept:      ' + CAST(@kept AS varchar(10));

DECLARE @tables TABLE (name sysname PRIMARY KEY);
INSERT @tables SELECT t.name FROM sys.tables t WHERE EXISTS (SELECT 1 FROM sys.columns c WHERE c.object_id = t.object_id AND c.name = 'TenantID');

DECLARE @n int, @sql nvarchar(400), @name sysname;
DECLARE @preview TABLE (name sysname, rows_to_remove int);
DECLARE pc CURSOR LOCAL FAST_FORWARD FOR SELECT name FROM @tables;
OPEN pc; FETCH NEXT FROM pc INTO @name;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = N'SELECT @n = COUNT(*) FROM [' + @name + N'] WHERE TenantID IN (SELECT TenantID FROM #victims)';
    EXEC sp_executesql @sql, N'@n int OUTPUT', @n = @n OUTPUT;
    IF @n > 0 INSERT @preview VALUES (@name, @n);
    FETCH NEXT FROM pc INTO @name;
END
CLOSE pc; DEALLOCATE pc;
SELECT 'rows in ' + name + ': ' + CAST(rows_to_remove AS varchar(12)) FROM @preview ORDER BY rows_to_remove DESC;
DECLARE @sumrows bigint = ISNULL((SELECT SUM(rows_to_remove) FROM @preview), 0);
PRINT 'Total rows to remove: ' + CAST(@sumrows AS varchar(20));

IF $(Apply) = 1
BEGIN
    BEGIN TRANSACTION;
    DECLARE @pass int = 0, @progress int = 1, @deleted int, @total bigint = 0;
    WHILE @progress > 0 AND @pass < 40
    BEGIN
        SET @progress = 0; SET @pass += 1;
        DECLARE dc CURSOR LOCAL FAST_FORWARD FOR SELECT name FROM @tables;
        OPEN dc; FETCH NEXT FROM dc INTO @name;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            BEGIN TRY
                SET @sql = N'DELETE FROM [' + @name + N'] WHERE TenantID IN (SELECT TenantID FROM #victims); SET @d = @@ROWCOUNT';
                EXEC sp_executesql @sql, N'@d int OUTPUT', @d = @deleted OUTPUT;
                IF @deleted > 0 BEGIN SET @progress = 1; SET @total += @deleted; END
            END TRY
            BEGIN CATCH
                -- a foreign key still points at these rows: a later pass removes the rows that point at them first
            END CATCH
            FETCH NEXT FROM dc INTO @name;
        END
        CLOSE dc; DEALLOCATE dc;
    END

    DECLARE @left bigint = 0;
    DECLARE lc CURSOR LOCAL FAST_FORWARD FOR SELECT name FROM @tables;
    OPEN lc; FETCH NEXT FROM lc INTO @name;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @sql = N'SELECT @n = COUNT(*) FROM [' + @name + N'] WHERE TenantID IN (SELECT TenantID FROM #victims)';
        EXEC sp_executesql @sql, N'@n int OUTPUT', @n = @n OUTPUT;
        SET @left += @n;
        FETCH NEXT FROM lc INTO @name;
    END
    CLOSE lc; DEALLOCATE lc;

    IF @left = 0
    BEGIN
        COMMIT TRANSACTION;
        PRINT 'DONE: ' + CAST(@total AS varchar(20)) + ' rows removed in ' + CAST(@pass AS varchar(5)) + ' passes.';
    END
    ELSE
    BEGIN
        ROLLBACK TRANSACTION;
        PRINT 'ROLLED BACK: ' + CAST(@left AS varchar(20)) + ' rows could not be removed. Nothing was changed.';
    END
END
ELSE PRINT 'Preview only. Run again with -v Apply=1 to delete.';

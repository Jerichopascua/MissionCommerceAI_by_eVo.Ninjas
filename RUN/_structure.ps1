# Shared by SAVE-SNAPSHOT and RESTORE-SNAPSHOT. Describes the STRUCTURE of the database (not its data): the applied migrations, every table and
# column, every stored procedure, view, function and trigger (by definition), and the indexes. Two databases with the same text have the same
# structure. A safety copy can only be restored into a database whose structure text is identical to the one saved beside it.
function Get-DatabaseStructure {
    param([string]$Database = 'PesoWeb_MissionDev')
    $q = @"
SET NOCOUNT ON;
SELECT 'migrations=' + ISNULL((SELECT STRING_AGG(CAST(MigrationId AS nvarchar(max)), ',') WITHIN GROUP (ORDER BY MigrationId) FROM __EFMigrationsHistory), '');
SELECT 'columns=' + CAST(COUNT(*) AS varchar(20)) + ':' + CAST(ISNULL(CHECKSUM_AGG(CHECKSUM(t.name, c.name, c.system_type_id, c.max_length, c.precision, c.scale, c.is_nullable)), 0) AS varchar(20))
  FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id WHERE t.is_ms_shipped = 0;
SELECT 'modules=' + CAST(COUNT(*) AS varchar(20)) + ':' + CAST(ISNULL(CHECKSUM_AGG(CHECKSUM(o.name, o.type, m.definition)), 0) AS varchar(20))
  FROM sys.sql_modules m JOIN sys.objects o ON o.object_id = m.object_id WHERE o.is_ms_shipped = 0;
SELECT 'indexes=' + CAST(COUNT(*) AS varchar(20)) + ':' + CAST(ISNULL(CHECKSUM_AGG(CHECKSUM(t.name, i.name, i.type, i.is_unique, i.is_primary_key)), 0) AS varchar(20))
  FROM sys.indexes i JOIN sys.tables t ON t.object_id = i.object_id WHERE t.is_ms_shipped = 0 AND i.type > 0;
"@
    $out = sqlcmd -S '(localdb)\MSSQLLocalDB' -d $Database -E -b -h -1 -W -Q $q
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the database structure.' }
    return (($out | Where-Object { $_ -and $_.Trim() }) -join "`n").Trim()
}

function Compare-Structure {
    # Returns $null when the same, otherwise a sentence saying what differs.
    param([string]$Saved, [string]$Now)
    if ($Saved.Trim() -eq $Now.Trim()) { return $null }
    $a = @{}; foreach ($l in $Saved -split "`n") { $k, $v = $l -split '=', 2; $a[$k] = $v }
    $b = @{}; foreach ($l in $Now -split "`n") { $k, $v = $l -split '=', 2; $b[$k] = $v }
    $d = @()
    if ($a['migrations'] -ne $b['migrations']) {
        $ma = @($a['migrations'] -split ','); $mb = @($b['migrations'] -split ',')
        $newer = @($mb | Where-Object { $_ -and $ma -notcontains $_ }).Count
        $older = @($ma | Where-Object { $_ -and $mb -notcontains $_ }).Count
        if ($newer) { $d += "$newer database migration(s) were applied after this copy was saved" }
        if ($older) { $d += "this copy has $older migration(s) the database does not" }
    }
    if ($a['columns'] -ne $b['columns']) { $d += 'tables or columns differ' }
    if ($a['modules'] -ne $b['modules']) { $d += 'stored procedures, views or functions differ' }
    if ($a['indexes'] -ne $b['indexes']) { $d += 'indexes differ' }
    if (-not $d) { $d = @('the structure differs') }
    return ($d -join '; ')
}
